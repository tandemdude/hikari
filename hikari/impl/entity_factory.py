# -*- coding: utf-8 -*-
# cython: language_level=3
# Copyright © Nekoka.tt 2019-2020
#
# This file is part of Hikari.
#
# Hikari is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hikari is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Hikari. If not, see <https://www.gnu.org/licenses/>.
"""Basic implementation of an entity factory for general bots and HTTP apps."""

from __future__ import annotations

__all__: typing.Final[typing.List[str]] = ["EntityFactoryComponentImpl"]

import datetime
import typing

from hikari.api import entity_factory
from hikari.api import rest as rest_app
from hikari.models import applications as application_models
from hikari.models import audit_logs as audit_log_models
from hikari.models import channels as channel_models
from hikari.models import colors as color_models
from hikari.models import embeds as embed_models
from hikari.models import emojis as emoji_models
from hikari.models import gateway as gateway_models
from hikari.models import guilds as guild_models
from hikari.models import invites as invite_models
from hikari.models import messages as message_models
from hikari.models import permissions as permission_models
from hikari.models import presences as presence_models
from hikari.models import users as user_models
from hikari.models import voices as voice_models
from hikari.models import webhooks as webhook_models
from hikari.utilities import data_binding
from hikari.utilities import date
from hikari.utilities import files
from hikari.utilities import snowflake
from hikari.utilities import undefined


def _deserialize_seconds_timedelta(seconds: typing.Union[str, int]) -> datetime.timedelta:
    return datetime.timedelta(seconds=int(seconds))


def _deserialize_day_timedelta(days: typing.Union[str, int]) -> datetime.timedelta:
    return datetime.timedelta(days=int(days))


def _deserialize_max_uses(age: int) -> typing.Optional[int]:
    return age if age > 0 else None


def _deserialize_max_age(seconds: int) -> typing.Optional[datetime.timedelta]:
    return datetime.timedelta(seconds=seconds) if seconds > 0 else None


class EntityFactoryComponentImpl(entity_factory.IEntityFactoryComponent):
    """Standard implementation for a serializer/deserializer.

    This will convert objects to/from JSON compatible representations.
    """

    __slots__: typing.Sequence[str] = (
        "_app",
        "_audit_log_entry_converters",
        "_audit_log_event_mapping",
        "_dm_channel_type_mapping",
        "_guild_channel_type_mapping",
    )

    def __init__(self, app: rest_app.IRESTApp) -> None:
        self._app = app
        self._audit_log_entry_converters: typing.Mapping[str, typing.Callable[[typing.Any], typing.Any]] = {
            audit_log_models.AuditLogChangeKey.OWNER_ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.AFK_CHANNEL_ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.AFK_TIMEOUT: _deserialize_seconds_timedelta,
            audit_log_models.AuditLogChangeKey.MFA_LEVEL: guild_models.GuildMFALevel,
            audit_log_models.AuditLogChangeKey.VERIFICATION_LEVEL: guild_models.GuildVerificationLevel,
            audit_log_models.AuditLogChangeKey.EXPLICIT_CONTENT_FILTER: guild_models.GuildExplicitContentFilterLevel,
            audit_log_models.AuditLogChangeKey.DEFAULT_MESSAGE_NOTIFICATIONS: guild_models.GuildMessageNotificationsLevel,
            # noqa: E501 - Line too long
            audit_log_models.AuditLogChangeKey.PRUNE_DELETE_DAYS: _deserialize_day_timedelta,
            audit_log_models.AuditLogChangeKey.WIDGET_CHANNEL_ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.POSITION: int,
            audit_log_models.AuditLogChangeKey.BITRATE: int,
            audit_log_models.AuditLogChangeKey.APPLICATION_ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.PERMISSIONS: permission_models.Permission,
            audit_log_models.AuditLogChangeKey.COLOR: color_models.Color,
            audit_log_models.AuditLogChangeKey.ALLOW: permission_models.Permission,
            audit_log_models.AuditLogChangeKey.DENY: permission_models.Permission,
            audit_log_models.AuditLogChangeKey.CHANNEL_ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.INVITER_ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.MAX_USES: _deserialize_max_uses,
            audit_log_models.AuditLogChangeKey.USES: int,
            audit_log_models.AuditLogChangeKey.MAX_AGE: _deserialize_max_age,
            audit_log_models.AuditLogChangeKey.ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.TYPE: str,
            audit_log_models.AuditLogChangeKey.ENABLE_EMOTICONS: bool,
            audit_log_models.AuditLogChangeKey.EXPIRE_BEHAVIOR: guild_models.IntegrationExpireBehaviour,
            audit_log_models.AuditLogChangeKey.EXPIRE_GRACE_PERIOD: _deserialize_day_timedelta,
            audit_log_models.AuditLogChangeKey.RATE_LIMIT_PER_USER: _deserialize_seconds_timedelta,
            audit_log_models.AuditLogChangeKey.SYSTEM_CHANNEL_ID: snowflake.Snowflake,
            audit_log_models.AuditLogChangeKey.ADD_ROLE_TO_MEMBER: self._deserialize_audit_log_change_roles,
            audit_log_models.AuditLogChangeKey.REMOVE_ROLE_FROM_MEMBER: self._deserialize_audit_log_change_roles,
            audit_log_models.AuditLogChangeKey.PERMISSION_OVERWRITES: self._deserialize_audit_log_overwrites,
        }
        self._audit_log_event_mapping: typing.Mapping[
            typing.Union[int, audit_log_models.AuditLogEventType],
            typing.Callable[[data_binding.JSONObject], audit_log_models.BaseAuditLogEntryInfo],
        ] = {
            audit_log_models.AuditLogEventType.CHANNEL_OVERWRITE_CREATE: self._deserialize_channel_overwrite_entry_info,
            audit_log_models.AuditLogEventType.CHANNEL_OVERWRITE_UPDATE: self._deserialize_channel_overwrite_entry_info,
            audit_log_models.AuditLogEventType.CHANNEL_OVERWRITE_DELETE: self._deserialize_channel_overwrite_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_PIN: self._deserialize_message_pin_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_UNPIN: self._deserialize_message_pin_entry_info,
            audit_log_models.AuditLogEventType.MEMBER_PRUNE: self._deserialize_member_prune_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_BULK_DELETE: self._deserialize_message_bulk_delete_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_DELETE: self._deserialize_message_delete_entry_info,
            audit_log_models.AuditLogEventType.MEMBER_DISCONNECT: self._deserialize_member_disconnect_entry_info,
            audit_log_models.AuditLogEventType.MEMBER_MOVE: self._deserialize_member_move_entry_info,
        }
        self._dm_channel_type_mapping = {
            channel_models.ChannelType.PRIVATE_TEXT: self.deserialize_private_text_channel,
            channel_models.ChannelType.PRIVATE_GROUP_TEXT: self.deserialize_private_group_text_channel,
        }
        self._guild_channel_type_mapping = {
            channel_models.ChannelType.GUILD_CATEGORY: self.deserialize_guild_category,
            channel_models.ChannelType.GUILD_TEXT: self.deserialize_guild_text_channel,
            channel_models.ChannelType.GUILD_NEWS: self.deserialize_guild_news_channel,
            channel_models.ChannelType.GUILD_STORE: self.deserialize_guild_store_channel,
            channel_models.ChannelType.GUILD_VOICE: self.deserialize_guild_voice_channel,
        }

    @property
    @typing.final
    def app(self) -> rest_app.IRESTApp:
        return self._app

    ######################
    # APPLICATION MODELS #
    ######################

    def deserialize_own_connection(self, payload: data_binding.JSONObject) -> application_models.OwnConnection:
        own_connection = application_models.OwnConnection()
        own_connection.id = payload["id"]  # this is not a snowflake!
        own_connection.name = payload["name"]
        own_connection.type = payload["type"]
        own_connection.is_revoked = payload["revoked"]

        if (integration_payloads := payload.get("integrations")) is not None:
            integrations = [self.deserialize_partial_integration(integration) for integration in integration_payloads]
        else:
            integrations = []
        own_connection.integrations = integrations

        own_connection.is_verified = payload["verified"]
        own_connection.is_friend_sync_enabled = payload["friend_sync"]
        own_connection.is_activity_visible = payload["show_activity"]
        # noinspection PyArgumentList
        own_connection.visibility = application_models.ConnectionVisibility(payload["visibility"])
        return own_connection

    def deserialize_own_guild(self, payload: data_binding.JSONObject) -> application_models.OwnGuild:
        own_guild = application_models.OwnGuild()
        own_guild.app = self._app
        self._set_partial_guild_attributes(payload, own_guild)
        own_guild.is_owner = bool(payload["owner"])
        raw_permissions = int(payload["permissions_new"])
        # noinspection PyArgumentList
        own_guild.my_permissions = permission_models.Permission(raw_permissions)
        return own_guild

    def deserialize_application(self, payload: data_binding.JSONObject) -> application_models.Application:
        application = application_models.Application()
        application.app = self._app
        application.id = snowflake.Snowflake(payload["id"])
        application.name = payload["name"]
        application.description = payload["description"]
        application.is_bot_public = payload.get("bot_public")
        application.is_bot_code_grant_required = payload.get("bot_require_code_grant")
        application.owner = self.deserialize_user(payload["owner"]) if "owner" in payload else None
        application.rpc_origins = payload["rpc_origins"] if "rpc_origins" in payload else None
        application.summary = payload["summary"]
        application.verify_key = bytes(payload["verify_key"], "utf-8") if "verify_key" in payload else None
        application.icon_hash = payload.get("icon")

        if (team_payload := payload.get("team")) is not None:
            team = application_models.Team()
            team.app = self._app
            team.id = snowflake.Snowflake(team_payload["id"])
            team.icon_hash = team_payload["icon"]

            members = {}
            for member_payload in team_payload["members"]:
                team_member = application_models.TeamMember()
                team_member.app = self.app
                # noinspection PyArgumentList
                team_member.membership_state = application_models.TeamMembershipState(
                    member_payload["membership_state"]
                )
                team_member.permissions = member_payload["permissions"]
                team_member.team_id = snowflake.Snowflake(member_payload["team_id"])
                team_member.user = self.deserialize_user(member_payload["user"])
                members[team_member.user.id] = team_member
            team.members = members

            team.owner_id = snowflake.Snowflake(team_payload["owner_user_id"])
            application.team = team
        else:
            application.team = None

        application.guild_id = snowflake.Snowflake(payload["guild_id"]) if "guild_id" in payload else None
        application.primary_sku_id = (
            snowflake.Snowflake(payload["primary_sku_id"]) if "primary_sku_id" in payload else None
        )
        application.slug = payload.get("slug")
        application.cover_image_hash = payload.get("cover_image")
        return application

    #####################
    # AUDIT LOGS MODELS #
    #####################

    def _deserialize_audit_log_change_roles(
        self, payload: data_binding.JSONArray
    ) -> typing.Mapping[snowflake.Snowflake, guild_models.PartialRole]:
        roles = {}
        for role_payload in payload:
            role = guild_models.PartialRole()
            role.app = self._app
            role.id = snowflake.Snowflake(role_payload["id"])
            role.name = role_payload["name"]
            roles[role.id] = role
        return roles

    def _deserialize_audit_log_overwrites(
        self, payload: data_binding.JSONArray
    ) -> typing.Mapping[snowflake.Snowflake, channel_models.PermissionOverwrite]:
        return {
            snowflake.Snowflake(overwrite["id"]): self.deserialize_permission_overwrite(overwrite)
            for overwrite in payload
        }

    @staticmethod
    def _deserialize_channel_overwrite_entry_info(
        payload: data_binding.JSONObject,
    ) -> audit_log_models.ChannelOverwriteEntryInfo:
        channel_overwrite_entry_info = audit_log_models.ChannelOverwriteEntryInfo()
        channel_overwrite_entry_info.id = snowflake.Snowflake(payload["id"])
        # noinspection PyArgumentList
        channel_overwrite_entry_info.type = channel_models.PermissionOverwriteType(payload["type"])
        channel_overwrite_entry_info.role_name = payload.get("role_name")
        return channel_overwrite_entry_info

    @staticmethod
    def _deserialize_message_pin_entry_info(payload: data_binding.JSONObject) -> audit_log_models.MessagePinEntryInfo:
        message_pin_entry_info = audit_log_models.MessagePinEntryInfo()
        message_pin_entry_info.channel_id = snowflake.Snowflake(payload["channel_id"])
        message_pin_entry_info.message_id = snowflake.Snowflake(payload["message_id"])
        return message_pin_entry_info

    @staticmethod
    def _deserialize_member_prune_entry_info(payload: data_binding.JSONObject) -> audit_log_models.MemberPruneEntryInfo:
        member_prune_entry_info = audit_log_models.MemberPruneEntryInfo()
        member_prune_entry_info.delete_member_days = datetime.timedelta(days=int(payload["delete_member_days"]))
        member_prune_entry_info.members_removed = int(payload["members_removed"])
        return member_prune_entry_info

    @staticmethod
    def _deserialize_message_bulk_delete_entry_info(
        payload: data_binding.JSONObject,
    ) -> audit_log_models.MessageBulkDeleteEntryInfo:
        message_bulk_delete_entry_info = audit_log_models.MessageBulkDeleteEntryInfo()
        message_bulk_delete_entry_info.count = int(payload["count"])
        return message_bulk_delete_entry_info

    @staticmethod
    def _deserialize_message_delete_entry_info(
        payload: data_binding.JSONObject,
    ) -> audit_log_models.MessageDeleteEntryInfo:
        message_delete_entry_info = audit_log_models.MessageDeleteEntryInfo()
        message_delete_entry_info.channel_id = snowflake.Snowflake(payload["channel_id"])
        message_delete_entry_info.count = int(payload["count"])
        return message_delete_entry_info

    @staticmethod
    def _deserialize_member_disconnect_entry_info(
        payload: data_binding.JSONObject,
    ) -> audit_log_models.MemberDisconnectEntryInfo:
        member_disconnect_entry_info = audit_log_models.MemberDisconnectEntryInfo()
        member_disconnect_entry_info.count = int(payload["count"])
        return member_disconnect_entry_info

    @staticmethod
    def _deserialize_member_move_entry_info(payload: data_binding.JSONObject) -> audit_log_models.MemberMoveEntryInfo:
        member_move_entry_info = audit_log_models.MemberMoveEntryInfo()
        member_move_entry_info.channel_id = snowflake.Snowflake(payload["channel_id"])
        member_move_entry_info.count = int(payload["count"])
        return member_move_entry_info

    @staticmethod
    def _deserialize_unrecognised_audit_log_entry_info(
        payload: data_binding.JSONObject,
    ) -> audit_log_models.UnrecognisedAuditLogEntryInfo:
        return audit_log_models.UnrecognisedAuditLogEntryInfo(payload)

    def deserialize_audit_log(self, payload: data_binding.JSONObject) -> audit_log_models.AuditLog:
        audit_log = audit_log_models.AuditLog()

        entries = {}
        for entry_payload in payload["audit_log_entries"]:
            entry = audit_log_models.AuditLogEntry()
            entry.app = self._app
            entry.id = snowflake.Snowflake(entry_payload["id"])

            if (target_id := entry_payload["target_id"]) is not None:
                target_id = snowflake.Snowflake(target_id)
            entry.target_id = target_id

            changes = []
            if (change_payloads := entry_payload.get("changes")) is not None:
                for change_payload in change_payloads:
                    change = audit_log_models.AuditLogChange()

                    try:
                        # noinspection PyArgumentList
                        change.key = audit_log_models.AuditLogChangeKey(change_payload["key"])
                    except ValueError:
                        change.key = change_payload["key"]

                    new_value = change_payload.get("new_value")
                    old_value = change_payload.get("old_value")
                    if value_converter := self._audit_log_entry_converters.get(change.key):
                        new_value = value_converter(new_value) if new_value is not None else None
                        old_value = value_converter(old_value) if old_value is not None else None
                    change.new_value = new_value
                    change.old_value = old_value

                    changes.append(change)
            entry.changes = changes

            if (user_id := entry_payload["user_id"]) is not None:
                user_id = snowflake.Snowflake(user_id)
            entry.user_id = user_id

            try:
                # noinspection PyArgumentList
                entry.action_type = audit_log_models.AuditLogEventType(entry_payload["action_type"])
            except ValueError:
                entry.action_type = entry_payload["action_type"]

            if (options := entry_payload.get("options")) is not None:
                option_converter = (
                    self._audit_log_event_mapping.get(entry.action_type)
                    or self._deserialize_unrecognised_audit_log_entry_info  # noqa: W503
                )
                options = option_converter(options)
            entry.options = options

            entry.reason = entry_payload.get("reason")
            entries[entry.id] = entry
        audit_log.entries = entries

        audit_log.integrations = {
            snowflake.Snowflake(integration["id"]): self.deserialize_partial_integration(integration)
            for integration in payload["integrations"]
        }
        audit_log.users = {snowflake.Snowflake(user["id"]): self.deserialize_user(user) for user in payload["users"]}
        audit_log.webhooks = {
            snowflake.Snowflake(webhook["id"]): self.deserialize_webhook(webhook) for webhook in payload["webhooks"]
        }
        return audit_log

    ##################
    # CHANNEL MODELS #
    ##################

    def deserialize_permission_overwrite(self, payload: data_binding.JSONObject) -> channel_models.PermissionOverwrite:
        # noinspection PyArgumentList
        permission_overwrite = channel_models.PermissionOverwrite(
            id=snowflake.Snowflake(payload["id"]), type=channel_models.PermissionOverwriteType(payload["type"]),
        )
        allow_raw = int(payload["allow_new"])
        deny_raw = int(payload["deny_new"])
        # noinspection PyArgumentList
        permission_overwrite.allow = permission_models.Permission(allow_raw)
        # noinspection PyArgumentList
        permission_overwrite.deny = permission_models.Permission(deny_raw)
        return permission_overwrite

    def serialize_permission_overwrite(self, overwrite: channel_models.PermissionOverwrite) -> data_binding.JSONObject:
        # https://github.com/discord/discord-api-docs/pull/1843/commits/470677363ba88fbc1fe79228821146c6d6b488b9
        # allow and deny can be strings instead now.
        return {
            "id": str(overwrite.id),
            "type": overwrite.type,
            "allow": str(int(overwrite.allow)),
            "deny": str(int(overwrite.deny)),
        }

    def _set_partial_channel_attributes(
        self, payload: data_binding.JSONObject, channel: channel_models.PartialChannel
    ) -> None:
        channel.app = self._app
        channel.id = snowflake.Snowflake(payload["id"])
        channel.name = payload.get("name")
        # noinspection PyArgumentList
        channel.type = channel_models.ChannelType(payload["type"])

    def deserialize_partial_channel(self, payload: data_binding.JSONObject) -> channel_models.PartialChannel:
        partial_channel = channel_models.PartialChannel()
        self._set_partial_channel_attributes(payload, partial_channel)
        return partial_channel

    def deserialize_private_text_channel(self, payload: data_binding.JSONObject) -> channel_models.PrivateTextChannel:
        channel = channel_models.PrivateTextChannel()
        self._set_partial_channel_attributes(payload, channel)

        if (last_message_id := payload["last_message_id"]) is not None:
            last_message_id = snowflake.Snowflake(last_message_id)
        channel.last_message_id = last_message_id

        channel.recipient = self.deserialize_user(payload["recipients"][0])
        return channel

    def deserialize_private_group_text_channel(
        self, payload: data_binding.JSONObject
    ) -> channel_models.GroupPrivateTextChannel:
        channel = channel_models.GroupPrivateTextChannel()
        self._set_partial_channel_attributes(payload, channel)

        if (last_message_id := payload["last_message_id"]) is not None:
            last_message_id = snowflake.Snowflake(last_message_id)
        channel.last_message_id = last_message_id

        channel.owner_id = snowflake.Snowflake(payload["owner_id"])
        channel.icon_hash = payload["icon"]

        if (nicks := payload.get("nicks")) is not None:
            nicknames = {snowflake.Snowflake(entry["id"]): entry["nick"] for entry in nicks}
        else:
            nicknames = {}
        channel.nicknames = nicknames

        channel.application_id = snowflake.Snowflake(payload["application_id"]) if "application_id" in payload else None
        channel.recipients = {
            snowflake.Snowflake(user["id"]): self.deserialize_user(user) for user in payload["recipients"]
        }
        return channel

    def _set_guild_channel_attributes(
        self,
        payload: data_binding.JSONObject,
        guild_channel: channel_models.GuildChannel,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake],
    ) -> None:
        self._set_partial_channel_attributes(payload, guild_channel)
        guild_channel.guild_id = (
            guild_id if guild_id is not undefined.UNDEFINED else snowflake.Snowflake(payload["guild_id"])
        )
        guild_channel.position = int(payload["position"])
        guild_channel.permission_overwrites = {
            snowflake.Snowflake(overwrite["id"]): self.deserialize_permission_overwrite(overwrite)
            for overwrite in payload["permission_overwrites"]
        }  # TODO: while snowflakes are guaranteed to be unique within their own resource, there is no guarantee for
        # across between resources (user and role in this case); while in practice we will not get overlap there is a
        # chance that this may happen in the future, would it be more sensible to use a Sequence here?
        guild_channel.is_nsfw = payload.get("nsfw")

        if (parent_id := payload.get("parent_id")) is not None:
            parent_id = snowflake.Snowflake(parent_id)
        guild_channel.parent_id = parent_id

    def deserialize_guild_category(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildCategory:
        category = channel_models.GuildCategory()
        self._set_guild_channel_attributes(payload, category, guild_id=guild_id)
        return category

    def deserialize_guild_text_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildTextChannel:
        guild_text_channel = channel_models.GuildTextChannel()
        self._set_guild_channel_attributes(payload, guild_text_channel, guild_id=guild_id)
        guild_text_channel.topic = payload["topic"]

        if (last_message_id := payload["last_message_id"]) is not None:
            last_message_id = snowflake.Snowflake(last_message_id)
        guild_text_channel.last_message_id = last_message_id

        # Usually this is 0 if unset, but some old channels made before the
        # rate_limit_per_user field was implemented will not have this field
        # at all if they have never had the rate limit changed...
        guild_text_channel.rate_limit_per_user = datetime.timedelta(seconds=payload.get("rate_limit_per_user", 0))

        if (last_pin_timestamp := payload.get("last_pin_timestamp")) is not None:
            last_pin_timestamp = date.iso8601_datetime_string_to_datetime(last_pin_timestamp)
        guild_text_channel.last_pin_timestamp = last_pin_timestamp

        return guild_text_channel

    def deserialize_guild_news_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildNewsChannel:
        guild_news_channel = channel_models.GuildNewsChannel()
        self._set_guild_channel_attributes(payload, guild_news_channel, guild_id=guild_id)
        guild_news_channel.topic = payload["topic"]

        if (last_message_id := payload["last_message_id"]) is not None:
            last_message_id = snowflake.Snowflake(last_message_id)
        guild_news_channel.last_message_id = last_message_id

        if (last_pin_timestamp := payload.get("last_pin_timestamp")) is not None:
            last_pin_timestamp = date.iso8601_datetime_string_to_datetime(last_pin_timestamp)
        guild_news_channel.last_pin_timestamp = last_pin_timestamp

        return guild_news_channel

    def deserialize_guild_store_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildStoreChannel:
        guild_store_channel = channel_models.GuildStoreChannel()
        self._set_guild_channel_attributes(payload, guild_store_channel, guild_id=guild_id)
        return guild_store_channel

    def deserialize_guild_voice_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildVoiceChannel:
        guild_voice_channel = channel_models.GuildVoiceChannel()
        self._set_guild_channel_attributes(payload, guild_voice_channel, guild_id=guild_id)
        guild_voice_channel.bitrate = int(payload["bitrate"])
        guild_voice_channel.user_limit = int(payload["user_limit"])
        return guild_voice_channel

    def deserialize_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.PartialChannel:
        channel_type = payload["type"]
        if channel_model := self._guild_channel_type_mapping.get(channel_type):
            # noinspection PyArgumentList
            return channel_model(payload, guild_id=guild_id)

        # noinspection PyArgumentList
        return self._dm_channel_type_mapping[channel_type](payload)

    ################
    # EMBED MODELS #
    ################

    def deserialize_embed(self, payload: data_binding.JSONObject) -> embed_models.Embed:
        # Keep these separate to aid debugging later.
        title = payload.get("title")
        description = payload.get("description")
        url = payload.get("url")
        color = color_models.Color(payload["color"]) if "color" in payload else None
        timestamp = date.iso8601_datetime_string_to_datetime(payload["timestamp"]) if "timestamp" in payload else None
        fields: typing.Optional[typing.MutableSequence[embed_models.EmbedField]] = None

        if image_payload := payload.get("image"):
            image: typing.Optional[embed_models.EmbedImage] = embed_models.EmbedImage(
                resource=files.ensure_resource(image_payload.get("url")),
                proxy_resource=files.ensure_resource(image_payload.get("proxy_url")),
                height=image_payload.get("height"),
                width=image_payload.get("width"),
            )
        else:
            image = None

        if thumbnail_payload := payload.get("thumbnail"):
            thumbnail: typing.Optional[embed_models.EmbedImage] = embed_models.EmbedImage(
                resource=files.ensure_resource(thumbnail_payload.get("url")),
                proxy_resource=files.ensure_resource(thumbnail_payload.get("proxy_url")),
                height=thumbnail_payload.get("height"),
                width=thumbnail_payload.get("width"),
            )
        else:
            thumbnail = None

        if video_payload := payload.get("video"):
            video: typing.Optional[embed_models.EmbedVideo] = embed_models.EmbedVideo(
                resource=files.ensure_resource(video_payload.get("url")),
                height=video_payload.get("height"),
                width=video_payload.get("width"),
            )
        else:
            video = None

        if provider_payload := payload.get("provider"):
            provider: typing.Optional[embed_models.EmbedProvider] = embed_models.EmbedProvider(
                name=provider_payload.get("name"), url=provider_payload.get("url")
            )
        else:
            provider = None

        if author_payload := payload.get("author"):
            if "icon_url" in author_payload:
                icon: typing.Optional[embed_models.EmbedResourceWithProxy] = embed_models.EmbedResourceWithProxy(
                    resource=files.ensure_resource(author_payload.get("icon_url")),
                    proxy_resource=files.ensure_resource(author_payload.get("proxy_icon_url")),
                )
            else:
                icon = None

            author: typing.Optional[embed_models.EmbedAuthor] = embed_models.EmbedAuthor(
                name=author_payload.get("name"), url=author_payload.get("url"), icon=icon,
            )
        else:
            author = None

        if footer_payload := payload.get("footer"):
            if "icon_url" in footer_payload:
                icon = embed_models.EmbedResourceWithProxy(
                    resource=files.ensure_resource(footer_payload.get("icon_url")),
                    proxy_resource=files.ensure_resource(footer_payload.get("proxy_icon_url")),
                )
            else:
                icon = None

            footer: typing.Optional[embed_models.EmbedFooter] = embed_models.EmbedFooter(
                text=footer_payload.get("text"), icon=icon
            )
        else:
            footer = None

        if fields_array := payload.get("fields"):
            fields = []
            for field_payload in fields_array:
                field = embed_models.EmbedField(
                    name=field_payload["name"], value=field_payload["value"], inline=field_payload.get("inline", False),
                )
                fields.append(field)

        return embed_models.Embed.from_received_embed(
            title=title,
            description=description,
            url=url,
            color=color,
            timestamp=timestamp,
            image=image,
            thumbnail=thumbnail,
            video=video,
            provider=provider,
            author=author,
            footer=footer,
            fields=fields,
        )

    def serialize_embed(  # noqa: C901
        self, embed: embed_models.Embed,
    ) -> typing.Tuple[data_binding.JSONObject, typing.List[files.Resource]]:

        payload: data_binding.JSONObject = {}
        uploads: typing.List[files.Resource] = []

        if embed.title is not None:
            payload["title"] = embed.title

        if embed.description is not None:
            payload["description"] = embed.description

        if embed.url is not None:
            payload["url"] = embed.url

        if embed.timestamp is not None:
            payload["timestamp"] = embed.timestamp.isoformat()

        if embed.color is not None:
            payload["color"] = int(embed.color)

        if embed.footer is not None:
            footer_payload: data_binding.JSONObject = {}

            if embed.footer.text is not None:
                footer_payload["text"] = embed.footer.text

            if embed.footer.icon is not None:
                if not isinstance(embed.footer.icon.resource, files.WebResource):
                    uploads.append(embed.footer.icon.resource)

                footer_payload["icon_url"] = embed.footer.icon.url

            payload["footer"] = footer_payload

        if embed.image is not None:
            image_payload: data_binding.JSONObject = {}

            if not isinstance(embed.image.resource, files.WebResource):
                uploads.append(embed.image.resource)

            image_payload["url"] = embed.image.url
            payload["image"] = image_payload

        if embed.thumbnail is not None:
            thumbnail_payload: data_binding.JSONObject = {}

            if not isinstance(embed.thumbnail.resource, files.WebResource):
                uploads.append(embed.thumbnail.resource)

            thumbnail_payload["url"] = embed.thumbnail.url
            payload["thumbnail"] = thumbnail_payload

        if embed.author is not None:
            author_payload: data_binding.JSONObject = {}

            if embed.author.name is not None:
                author_payload["name"] = embed.author.name

            if embed.author.url is not None:
                author_payload["url"] = embed.author.url

            if embed.author.icon is not None:
                if not isinstance(embed.author.icon.resource, files.WebResource):
                    uploads.append(embed.author.icon.resource)
                author_payload["icon_url"] = embed.author.icon.url

            payload["author"] = author_payload

        if embed.fields:
            field_payloads: data_binding.JSONArray = []
            for i, field in enumerate(embed.fields):

                # Yep, this is technically two unreachable branches. However, this is an incredibly
                # common mistake to make when working with embeds and not using a static type
                # checker, so I have added these as additional safeguards for UX and ease
                # of debugging. The case that there are `None` should be detected immediately by
                # static type checkers, regardless.

                name = str(field.name) if field.name is not None else None  # type: ignore[unreachable]
                value = str(field.value) if field.value is not None else None  # type: ignore[unreachable]

                if name is None:
                    raise TypeError(f"in embed.fields[{i}].name - cannot have `None`")
                if not name:
                    raise TypeError(f"in embed.fields[{i}].name - cannot have empty string")
                if not name.strip():
                    raise TypeError(f"in embed.fields[{i}].name - cannot have only whitespace")

                if value is None:
                    raise TypeError(f"in embed.fields[{i}].value - cannot have `None`")
                if not value:
                    raise TypeError(f"in embed.fields[{i}].value - cannot have empty string")
                if not value.strip():
                    raise TypeError(f"in embed.fields[{i}].value - cannot have only whitespace")

                # Name and value always have to be specified; we can always
                # send a default `inline` value also just to keep this simpler.
                field_payloads.append({"name": name, "value": value, "inline": field.is_inline})
            payload["fields"] = field_payloads

        return payload, uploads

    ################
    # EMOJI MODELS #
    ################

    def deserialize_unicode_emoji(self, payload: data_binding.JSONObject) -> emoji_models.UnicodeEmoji:
        unicode_emoji = emoji_models.UnicodeEmoji()
        unicode_emoji.name = payload["name"]
        return unicode_emoji

    def deserialize_custom_emoji(self, payload: data_binding.JSONObject) -> emoji_models.CustomEmoji:
        custom_emoji = emoji_models.CustomEmoji()
        custom_emoji.app = self._app
        custom_emoji.id = snowflake.Snowflake(payload["id"])
        custom_emoji.name = payload["name"]
        custom_emoji.is_animated = payload.get("animated", False)
        return custom_emoji

    def deserialize_known_custom_emoji(
        self, payload: data_binding.JSONObject, *, guild_id: snowflake.Snowflake
    ) -> emoji_models.KnownCustomEmoji:
        known_custom_emoji = emoji_models.KnownCustomEmoji()
        known_custom_emoji.app = self._app
        known_custom_emoji.id = snowflake.Snowflake(payload["id"])
        # noinspection PyPropertyAccess
        known_custom_emoji.name = payload["name"]
        known_custom_emoji.is_animated = payload.get("animated", False)
        known_custom_emoji.guild_id = guild_id
        known_custom_emoji.role_ids = (
            [snowflake.Snowflake(role_id) for role_id in payload["roles"]] if "roles" in payload else []
        )

        if (user := payload.get("user")) is not None:
            user = self.deserialize_user(user)
        known_custom_emoji.user = user

        known_custom_emoji.is_colons_required = payload["require_colons"]
        known_custom_emoji.is_managed = payload["managed"]
        known_custom_emoji.is_available = payload["available"]
        return known_custom_emoji

    def deserialize_emoji(
        self, payload: data_binding.JSONObject
    ) -> typing.Union[emoji_models.UnicodeEmoji, emoji_models.CustomEmoji]:
        if payload.get("id") is not None:
            return self.deserialize_custom_emoji(payload)

        return self.deserialize_unicode_emoji(payload)

    ##################
    # GATEWAY MODELS #
    ##################

    def deserialize_gateway_bot(self, payload: data_binding.JSONObject) -> gateway_models.GatewayBot:
        session_start_limit_payload = payload["session_start_limit"]
        session_start_limit = gateway_models.SessionStartLimit(
            total=int(session_start_limit_payload["total"]),
            remaining=int(session_start_limit_payload["remaining"]),
            reset_after=datetime.timedelta(milliseconds=session_start_limit_payload["reset_after"]),
            # I do not trust that this may never be zero for some unknown reason. If it was 0, it
            # would hang the application on start up, so I enforce it is at least 1.
            max_concurrency=max(session_start_limit_payload.get("max_concurrency", 0), 1),
        )
        return gateway_models.GatewayBot(
            url=payload["url"], shard_count=int(payload["shards"]), session_start_limit=session_start_limit,
        )

    ################
    # GUILD MODELS #
    ################

    def deserialize_guild_widget(self, payload: data_binding.JSONObject) -> guild_models.GuildWidget:
        guild_widget = guild_models.GuildWidget()
        guild_widget.app = self._app

        if (channel_id := payload["channel_id"]) is not None:
            channel_id = snowflake.Snowflake(channel_id)
        guild_widget.channel_id = channel_id

        guild_widget.is_enabled = payload["enabled"]
        return guild_widget

    def deserialize_member(
        self,
        payload: data_binding.JSONObject,
        *,
        user: undefined.UndefinedOr[user_models.User] = undefined.UNDEFINED,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> guild_models.Member:
        guild_member = guild_models.Member()
        guild_member.user = typing.cast(user_models.UserImpl, user or self.deserialize_user(payload["user"]))
        guild_member.guild_id = (
            snowflake.Snowflake(payload["guild_id"]) if guild_id is undefined.UNDEFINED else guild_id
        )
        guild_member.role_ids = [snowflake.Snowflake(role_id) for role_id in payload["roles"]]

        joined_at = payload.get("joined_at")
        guild_member.joined_at = (
            date.iso8601_datetime_string_to_datetime(joined_at) if joined_at is not None else undefined.UNDEFINED
        )

        guild_member.nickname = payload["nick"] if "nick" in payload else undefined.UNDEFINED

        if "premium_since" in payload:
            raw_premium_since = payload["premium_since"]
            guild_member.premium_since = (
                date.iso8601_datetime_string_to_datetime(raw_premium_since) if raw_premium_since is not None else None
            )
        else:
            guild_member.premium_since = undefined.UNDEFINED

        guild_member.is_deaf = payload["deaf"] if "deaf" in payload else undefined.UNDEFINED
        guild_member.is_mute = payload["mute"] if "mute" in payload else undefined.UNDEFINED
        return guild_member

    def deserialize_role(
        self, payload: data_binding.JSONObject, *, guild_id: snowflake.Snowflake,
    ) -> guild_models.Role:
        guild_role = guild_models.Role()
        guild_role.app = self._app
        guild_role.id = snowflake.Snowflake(payload["id"])
        guild_role.guild_id = guild_id
        guild_role.name = payload["name"]
        guild_role.color = color_models.Color(payload["color"])
        guild_role.is_hoisted = payload["hoist"]
        guild_role.position = int(payload["position"])

        # https://github.com/discord/discord-api-docs/pull/1843/commits/470677363ba88fbc1fe79228821146c6d6b488b9
        raw_permissions = int(payload["permissions_new"])
        # noinspection PyArgumentList
        guild_role.permissions = permission_models.Permission(raw_permissions)
        guild_role.is_managed = payload["managed"]
        guild_role.is_mentionable = payload["mentionable"]
        return guild_role

    @staticmethod
    def _set_partial_integration_attributes(
        payload: data_binding.JSONObject, integration: guild_models.PartialIntegration
    ) -> None:
        integration.id = snowflake.Snowflake(payload["id"])
        integration.name = payload["name"]
        integration.type = payload["type"]
        account_payload = payload["account"]
        account = guild_models.IntegrationAccount()
        account.id = account_payload["id"]
        account.name = account_payload["name"]
        integration.account = account

    def deserialize_partial_integration(self, payload: data_binding.JSONObject) -> guild_models.PartialIntegration:
        partial_integration = guild_models.PartialIntegration()
        self._set_partial_integration_attributes(payload, partial_integration)
        return partial_integration

    def deserialize_integration(self, payload: data_binding.JSONObject) -> guild_models.Integration:
        guild_integration = guild_models.Integration()
        self._set_partial_integration_attributes(payload, guild_integration)
        guild_integration.is_enabled = payload["enabled"]
        guild_integration.is_syncing = payload["syncing"]

        if (role_id := payload.get("role_id")) is not None:
            role_id = snowflake.Snowflake(role_id)
        guild_integration.role_id = role_id

        guild_integration.is_emojis_enabled = payload.get("enable_emoticons")
        # noinspection PyArgumentList
        guild_integration.expire_behavior = guild_models.IntegrationExpireBehaviour(payload["expire_behavior"])
        guild_integration.expire_grace_period = datetime.timedelta(days=payload["expire_grace_period"])
        guild_integration.user = self.deserialize_user(payload["user"])

        if (last_synced_at := payload.get("synced_at")) is not None:
            last_synced_at = date.iso8601_datetime_string_to_datetime(last_synced_at)
        guild_integration.last_synced_at = last_synced_at

        return guild_integration

    def deserialize_guild_member_ban(self, payload: data_binding.JSONObject) -> guild_models.GuildMemberBan:
        guild_member_ban = guild_models.GuildMemberBan()
        guild_member_ban.reason = payload["reason"]
        guild_member_ban.user = self.deserialize_user(payload["user"])
        return guild_member_ban

    def deserialize_unavailable_guild(self, payload: data_binding.JSONObject) -> guild_models.UnavailableGuild:
        unavailable_guild = guild_models.UnavailableGuild()
        unavailable_guild.id = snowflake.Snowflake(payload["id"])
        return unavailable_guild

    @staticmethod
    def _set_partial_guild_attributes(payload: data_binding.JSONObject, guild: guild_models.PartialGuild) -> None:
        guild.id = snowflake.Snowflake(payload["id"])
        guild.name = payload["name"]
        guild.icon_hash = payload["icon"]

        features = []
        for feature in payload["features"]:
            try:
                # noinspection PyArgumentList
                features.append(guild_models.GuildFeature(feature))
            except ValueError:
                features.append(feature)
        guild.features = features

    def deserialize_guild_preview(self, payload: data_binding.JSONObject) -> guild_models.GuildPreview:
        guild_preview = guild_models.GuildPreview()
        guild_preview.app = self._app
        self._set_partial_guild_attributes(payload, guild_preview)
        guild_preview.splash_hash = payload["splash"]
        guild_preview.discovery_splash_hash = payload["discovery_splash"]
        guild_preview.emojis = {
            snowflake.Snowflake(emoji["id"]): self.deserialize_known_custom_emoji(emoji, guild_id=guild_preview.id)
            for emoji in payload["emojis"]
        }
        guild_preview.approximate_presence_count = int(payload["approximate_presence_count"])
        guild_preview.approximate_member_count = int(payload["approximate_member_count"])
        guild_preview.description = payload["description"]
        return guild_preview

    def _set_guild_attributes(self, payload: data_binding.JSONObject, guild: guild_models.Guild) -> None:
        self._set_partial_guild_attributes(payload, guild)
        guild.app = self._app
        guild.splash_hash = payload["splash"]
        guild.discovery_splash_hash = payload["discovery_splash"]
        guild.owner_id = snowflake.Snowflake(payload["owner_id"])
        # noinspection PyArgumentList

        guild.region = payload["region"]

        afk_channel_id = payload["afk_channel_id"]
        guild.afk_channel_id = snowflake.Snowflake(afk_channel_id) if afk_channel_id is not None else None

        guild.afk_timeout = datetime.timedelta(seconds=payload["afk_timeout"])

        # noinspection PyArgumentList
        guild.verification_level = guild_models.GuildVerificationLevel(payload["verification_level"])
        # noinspection PyArgumentList
        guild.default_message_notifications = guild_models.GuildMessageNotificationsLevel(
            payload["default_message_notifications"]
        )
        # noinspection PyArgumentList
        guild.explicit_content_filter = guild_models.GuildExplicitContentFilterLevel(payload["explicit_content_filter"])

        guild.mfa_level = guild_models.GuildMFALevel(payload["mfa_level"])

        application_id = payload["application_id"]
        guild.application_id = snowflake.Snowflake(application_id) if application_id is not None else None

        widget_channel_id = payload.get("widget_channel_id")
        guild.widget_channel_id = snowflake.Snowflake(widget_channel_id) if widget_channel_id is not None else None

        system_channel_id = payload["system_channel_id"]
        guild.system_channel_id = snowflake.Snowflake(system_channel_id) if system_channel_id is not None else None

        guild.is_widget_enabled = payload["widget_enabled"] if "widget_enabled" in payload else None
        # noinspection PyArgumentList
        guild.system_channel_flags = guild_models.GuildSystemChannelFlag(payload["system_channel_flags"])

        rules_channel_id = payload["rules_channel_id"]
        guild.rules_channel_id = snowflake.Snowflake(rules_channel_id) if rules_channel_id is not None else None

        max_presences = payload.get("max_presences")
        guild.max_presences = int(max_presences) if max_presences is not None else None

        guild.max_members = int(payload["max_members"]) if "max_members" in payload else None
        guild.max_video_channel_users = (
            int(payload["max_video_channel_users"]) if "max_video_channel_users" in payload else None
        )
        guild.vanity_url_code = payload["vanity_url_code"]
        guild.description = payload["description"]
        guild.banner_hash = payload["banner"]
        # noinspection PyArgumentList
        guild.premium_tier = guild_models.GuildPremiumTier(payload["premium_tier"])

        guild.premium_subscription_count = payload.get("premium_subscription_count")

        guild.preferred_locale = payload["preferred_locale"]

        public_updates_channel_id = payload["public_updates_channel_id"]
        guild.public_updates_channel_id = (
            snowflake.Snowflake(public_updates_channel_id) if public_updates_channel_id is not None else None
        )

    def deserialize_rest_guild(self, payload: data_binding.JSONObject) -> guild_models.RESTGuild:
        guild = guild_models.RESTGuild()
        self._set_guild_attributes(payload, guild)

        guild.approximate_member_count = (
            int(payload["approximate_member_count"]) if "approximate_member_count" in payload else None
        )
        guild.approximate_active_member_count = (
            int(payload["approximate_presence_count"]) if "approximate_presence_count" in payload else None
        )

        guild._roles = {
            snowflake.Snowflake(role["id"]): self.deserialize_role(role, guild_id=guild.id) for role in payload["roles"]
        }
        guild._emojis = {
            snowflake.Snowflake(emoji["id"]): self.deserialize_known_custom_emoji(emoji, guild_id=guild.id)
            for emoji in payload["emojis"]
        }

        return guild

    def deserialize_gateway_guild(self, payload: data_binding.JSONObject) -> entity_factory.GatewayGuildDefinition:
        guild = guild_models.GatewayGuild()
        self._set_guild_attributes(payload, guild)

        guild.my_permissions = (
            permission_models.Permission(payload["permissions"]) if "permissions" in payload else None
        )
        guild.is_large = payload["large"] if "large" in payload else None
        guild.joined_at = (
            date.iso8601_datetime_string_to_datetime(payload["joined_at"]) if "joined_at" in payload else None
        )
        guild.member_count = int(payload["member_count"]) if "member_count" in payload else None

        members: typing.Union[typing.MutableMapping[snowflake.Snowflake, guild_models.Member], None]
        if "members" in payload:
            members = {}

            for member_payload in payload["members"]:
                member = self.deserialize_member(member_payload, guild_id=guild.id)
                members[member.user.id] = member

        else:
            members = None

        channels: typing.Union[typing.MutableMapping[snowflake.Snowflake, channel_models.GuildChannel], None]
        if "channels" in payload:
            channels = {}

            for channel_payload in payload["channels"]:
                channel = typing.cast(
                    "channel_models.GuildChannel", self.deserialize_channel(channel_payload, guild_id=guild.id)
                )
                channels[channel.id] = channel

        else:
            channels = None

        presences: typing.Union[typing.MutableMapping[snowflake.Snowflake, presence_models.MemberPresence], None]
        if "presences" in payload:
            presences = {}

            for presence_payload in payload["presences"]:
                presence = self.deserialize_member_presence(presence_payload, guild_id=guild.id)
                presences[presence.user_id] = presence

        else:
            presences = None

        voice_states: typing.Union[typing.MutableMapping[snowflake.Snowflake, voice_models.VoiceState], None]
        if "voice_states" in payload:
            voice_states = {}
            assert members is not None

            for voice_state_payload in payload["voice_states"]:
                member = members[snowflake.Snowflake(voice_state_payload["user_id"])]
                voice_state = self.deserialize_voice_state(voice_state_payload, guild_id=guild.id, member=member)
                voice_states[voice_state.user_id] = voice_state

        else:
            voice_states = None

        roles = {
            snowflake.Snowflake(role["id"]): self.deserialize_role(role, guild_id=guild.id) for role in payload["roles"]
        }
        emojis = {
            snowflake.Snowflake(emoji["id"]): self.deserialize_known_custom_emoji(emoji, guild_id=guild.id)
            for emoji in payload["emojis"]
        }

        return entity_factory.GatewayGuildDefinition(guild, channels, members, presences, roles, emojis, voice_states)

    #################
    # INVITE MODELS #
    #################

    def deserialize_vanity_url(self, payload: data_binding.JSONObject) -> invite_models.VanityURL:
        vanity_url = invite_models.VanityURL()
        vanity_url.app = self._app
        vanity_url.code = payload["code"]
        vanity_url.uses = int(payload["uses"])
        return vanity_url

    def _set_invite_attributes(self, payload: data_binding.JSONObject, invite: invite_models.Invite) -> None:
        invite.code = payload["code"]

        if "guild" in payload:
            guild_payload = payload["guild"]
            guild = invite_models.InviteGuild()
            guild.app = self._app
            self._set_partial_guild_attributes(guild_payload, guild)
            guild.splash_hash = guild_payload["splash"]
            guild.banner_hash = guild_payload["banner"]
            guild.description = guild_payload["description"]
            # noinspection PyArgumentList
            guild.verification_level = guild_models.GuildVerificationLevel(guild_payload["verification_level"])
            guild.vanity_url_code = guild_payload["vanity_url_code"]
            invite.guild = guild
            invite.guild_id = guild.id
        elif "guild_id" in payload:
            invite.guild = None
            invite.guild_id = snowflake.Snowflake(payload["guild_id"])
        else:
            invite.guild = invite.guild_id = None

        if (channel := payload.get("channel")) is not None:
            channel = self.deserialize_partial_channel(channel)
            channel_id = channel.id
        else:
            channel_id = snowflake.Snowflake(payload["channel_id"])
        invite.channel = channel
        invite.channel_id = channel_id

        invite.inviter = self.deserialize_user(payload["inviter"]) if "inviter" in payload else None
        invite.target_user = self.deserialize_user(payload["target_user"]) if "target_user" in payload else None
        # noinspection PyArgumentList
        invite.target_user_type = (
            invite_models.TargetUserType(payload["target_user_type"]) if "target_user_type" in payload else None
        )
        invite.approximate_presence_count = (
            int(payload["approximate_presence_count"]) if "approximate_presence_count" in payload else None
        )
        invite.approximate_member_count = (
            int(payload["approximate_member_count"]) if "approximate_member_count" in payload else None
        )

    def deserialize_invite(self, payload: data_binding.JSONObject) -> invite_models.Invite:
        invite = invite_models.Invite()
        invite.app = self._app
        self._set_invite_attributes(payload, invite)
        return invite

    def deserialize_invite_with_metadata(self, payload: data_binding.JSONObject) -> invite_models.InviteWithMetadata:
        invite_with_metadata = invite_models.InviteWithMetadata()
        invite_with_metadata.app = self._app
        self._set_invite_attributes(payload, invite_with_metadata)
        invite_with_metadata.uses = int(payload["uses"])
        invite_with_metadata.max_uses = int(payload["max_uses"])
        max_age = payload["max_age"]
        invite_with_metadata.max_age = datetime.timedelta(seconds=max_age) if max_age > 0 else None
        invite_with_metadata.is_temporary = payload["temporary"]
        invite_with_metadata.created_at = date.iso8601_datetime_string_to_datetime(payload["created_at"])
        return invite_with_metadata

    ##################
    # MESSAGE MODELS #
    ##################

    def deserialize_partial_message(self, payload: data_binding.JSONObject) -> message_models.PartialMessage:
        partial_message = message_models.PartialMessage()
        partial_message.app = self._app
        partial_message.id = snowflake.Snowflake(payload["id"])
        partial_message.channel_id = snowflake.Snowflake(payload["channel_id"])
        partial_message.guild_id = (
            snowflake.Snowflake(payload["guild_id"]) if "guild_id" in payload else undefined.UNDEFINED
        )
        partial_message.author = (
            self.deserialize_user(payload["author"]) if "author" in payload else undefined.UNDEFINED
        )
        partial_message.member = (
            self.deserialize_member(payload["member"], user=partial_message.author, guild_id=partial_message.guild_id)
            if "member" in payload
            else undefined.UNDEFINED
        )
        partial_message.content = payload["content"] if "content" in payload else undefined.UNDEFINED
        partial_message.timestamp = (
            date.iso8601_datetime_string_to_datetime(payload["timestamp"])
            if "timestamp" in payload
            else undefined.UNDEFINED
        )

        if "edited_timestamp" in payload:
            if (edited_timestamp := payload["edited_timestamp"]) is not None:
                edited_timestamp = date.iso8601_datetime_string_to_datetime(edited_timestamp)
            else:
                edited_timestamp = None
        else:
            edited_timestamp = undefined.UNDEFINED

        partial_message.edited_timestamp = edited_timestamp

        partial_message.is_tts = payload["tts"] if "tts" in payload else undefined.UNDEFINED
        partial_message.is_mentioning_everyone = (
            payload["mention_everyone"] if "mention_everyone" in payload else undefined.UNDEFINED
        )
        partial_message.user_mentions = (
            [snowflake.Snowflake(mention["id"]) for mention in payload["mentions"]]
            if "mentions" in payload
            else undefined.UNDEFINED
        )
        partial_message.role_mentions = (
            [snowflake.Snowflake(mention) for mention in payload["mention_roles"]]
            if "mention_roles" in payload
            else undefined.UNDEFINED
        )
        partial_message.channel_mentions = (
            [snowflake.Snowflake(mention["id"]) for mention in payload["mention_channels"]]
            if "mention_channels" in payload
            else undefined.UNDEFINED
        )

        if "attachments" in payload:
            attachments = []
            for attachment_payload in payload["attachments"]:
                attachment = message_models.Attachment()
                attachment.id = snowflake.Snowflake(attachment_payload["id"])
                attachment.filename = attachment_payload["filename"]
                attachment.size = int(attachment_payload["size"])
                attachment.url = attachment_payload["url"]
                attachment.proxy_url = attachment_payload["proxy_url"]
                attachment.height = attachment_payload.get("height")
                attachment.width = attachment_payload.get("width")
                attachments.append(attachment)
            partial_message.attachments = attachments
        else:
            partial_message.attachments = undefined.UNDEFINED

        partial_message.embeds = (
            [self.deserialize_embed(embed) for embed in payload["embeds"]]
            if "embeds" in payload
            else undefined.UNDEFINED
        )

        if "reactions" in payload:
            reactions = []
            for reaction_payload in payload["reactions"]:
                reaction = message_models.Reaction()
                reaction.count = int(reaction_payload["count"])
                reaction.emoji = self.deserialize_emoji(reaction_payload["emoji"])
                reaction.is_me = reaction_payload["me"]
                reactions.append(reaction)
            partial_message.reactions = reactions
        else:
            partial_message.reactions = undefined.UNDEFINED

        partial_message.is_pinned = payload["pinned"] if "pinned" in payload else undefined.UNDEFINED
        partial_message.webhook_id = (
            snowflake.Snowflake(payload["webhook_id"]) if "webhook_id" in payload else undefined.UNDEFINED
        )
        # noinspection PyArgumentList
        partial_message.type = message_models.MessageType(payload["type"]) if "type" in payload else undefined.UNDEFINED

        if "activity" in payload:
            activity_payload = payload["activity"]
            activity = message_models.MessageActivity()
            # noinspection PyArgumentList
            activity.type = message_models.MessageActivityType(activity_payload["type"])
            activity.party_id = activity_payload.get("party_id")
            partial_message.activity = activity
        else:
            partial_message.activity = undefined.UNDEFINED

        partial_message.application = (
            self.deserialize_application(payload["application"]) if "application" in payload else undefined.UNDEFINED
        )

        if "message_reference" in payload:
            crosspost_payload = payload["message_reference"]
            crosspost = message_models.MessageCrosspost()
            crosspost.app = self._app
            crosspost.id = (
                snowflake.Snowflake(crosspost_payload["message_id"]) if "message_id" in crosspost_payload else None
            )
            crosspost.channel_id = snowflake.Snowflake(crosspost_payload["channel_id"])
            crosspost.guild_id = (
                snowflake.Snowflake(crosspost_payload["guild_id"]) if "guild_id" in crosspost_payload else None
            )
            partial_message.message_reference = crosspost
        else:
            partial_message.message_reference = undefined.UNDEFINED

        # noinspection PyArgumentList
        partial_message.flags = (
            message_models.MessageFlag(payload["flags"]) if "flags" in payload else undefined.UNDEFINED
        )
        partial_message.nonce = payload["nonce"] if "nonce" in payload else undefined.UNDEFINED
        return partial_message

    def deserialize_message(self, payload: data_binding.JSONObject) -> message_models.Message:
        message = message_models.Message()
        message.app = self._app
        message.id = snowflake.Snowflake(payload["id"])
        message.channel_id = snowflake.Snowflake(payload["channel_id"])
        message.guild_id = snowflake.Snowflake(payload["guild_id"]) if "guild_id" in payload else None
        message.author = self.deserialize_user(payload["author"])
        message.member = (
            self.deserialize_member(
                payload["member"], guild_id=typing.cast(snowflake.Snowflake, message.guild_id), user=message.author
            )
            if "member" in payload
            else None
        )
        message.content = payload["content"]
        message.timestamp = date.iso8601_datetime_string_to_datetime(payload["timestamp"])

        if (edited_timestamp := payload["edited_timestamp"]) is not None:
            edited_timestamp = date.iso8601_datetime_string_to_datetime(edited_timestamp)
        message.edited_timestamp = edited_timestamp

        message.is_tts = payload["tts"]
        message.is_mentioning_everyone = payload["mention_everyone"]
        message.user_mentions = [snowflake.Snowflake(mention["id"]) for mention in payload["mentions"]]
        message.role_mentions = [snowflake.Snowflake(mention) for mention in payload["mention_roles"]]
        message.channel_mentions = (
            [snowflake.Snowflake(mention["id"]) for mention in payload["mention_channels"]]
            if "mention_channels" in payload
            else []
        )

        attachments = []
        for attachment_payload in payload["attachments"]:
            attachment = message_models.Attachment()
            attachment.id = snowflake.Snowflake(attachment_payload["id"])
            attachment.filename = attachment_payload["filename"]
            attachment.size = int(attachment_payload["size"])
            attachment.url = attachment_payload["url"]
            attachment.proxy_url = attachment_payload["proxy_url"]
            attachment.height = attachment_payload.get("height")
            attachment.width = attachment_payload.get("width")
            attachments.append(attachment)
        message.attachments = attachments

        message.embeds = [self.deserialize_embed(embed) for embed in payload["embeds"]]

        reactions = []
        if "reactions" in payload:
            for reaction_payload in payload["reactions"]:
                reaction = message_models.Reaction()
                reaction.count = int(reaction_payload["count"])
                reaction.emoji = self.deserialize_emoji(reaction_payload["emoji"])
                reaction.is_me = reaction_payload["me"]
                reactions.append(reaction)
        message.reactions = reactions

        message.is_pinned = payload["pinned"]
        message.webhook_id = snowflake.Snowflake(payload["webhook_id"]) if "webhook_id" in payload else None
        # noinspection PyArgumentList
        message.type = message_models.MessageType(payload["type"])

        if "activity" in payload:
            activity_payload = payload["activity"]
            activity = message_models.MessageActivity()
            # noinspection PyArgumentList
            activity.type = message_models.MessageActivityType(activity_payload["type"])
            activity.party_id = activity_payload.get("party_id")
            message.activity = activity
        else:
            message.activity = None

        message.application = self.deserialize_application(payload["application"]) if "application" in payload else None

        if "message_reference" in payload:
            crosspost_payload = payload["message_reference"]
            crosspost = message_models.MessageCrosspost()
            crosspost.app = self._app
            crosspost.id = (
                snowflake.Snowflake(crosspost_payload["message_id"]) if "message_id" in crosspost_payload else None
            )
            crosspost.channel_id = snowflake.Snowflake(crosspost_payload["channel_id"])
            crosspost.guild_id = (
                snowflake.Snowflake(crosspost_payload["guild_id"]) if "guild_id" in crosspost_payload else None
            )
            message.message_reference = crosspost
        else:
            message.message_reference = None

        # noinspection PyArgumentList
        message.flags = message_models.MessageFlag(payload["flags"]) if "flags" in payload else None
        message.nonce = payload.get("nonce")
        return message

    ###################
    # PRESENCE MODELS #
    ###################

    def deserialize_member_presence(  # noqa: CFQ001  # TODO: what's CFQ001?
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
    ) -> presence_models.MemberPresence:
        presence = presence_models.MemberPresence()
        presence.app = self._app
        presence.user_id = snowflake.Snowflake(payload["user"]["id"])
        presence.role_ids = (
            [snowflake.Snowflake(role_id) for role_id in payload["roles"]] if "roles" in payload else None
        )
        presence.guild_id = (
            guild_id if guild_id is not undefined.UNDEFINED else snowflake.Snowflake(payload["guild_id"])
        )
        # noinspection PyArgumentList
        presence.visible_status = presence_models.Status(payload["status"])

        activities = []
        for activity_payload in payload["activities"]:
            # noinspection PyArgumentList
            activity = presence_models.RichActivity(
                name=activity_payload["name"],
                type=presence_models.ActivityType(activity_payload["type"]),
                url=activity_payload.get("url"),
            )

            activity.created_at = date.unix_epoch_to_datetime(activity_payload["created_at"])

            timestamps = None
            if "timestamps" in activity_payload:
                timestamps_payload = activity_payload["timestamps"]
                timestamps = presence_models.ActivityTimestamps()
                timestamps.start = (
                    date.unix_epoch_to_datetime(timestamps_payload["start"]) if "start" in timestamps_payload else None
                )
                timestamps.end = (
                    date.unix_epoch_to_datetime(timestamps_payload["end"]) if "end" in timestamps_payload else None
                )
            activity.timestamps = timestamps

            activity.application_id = (
                snowflake.Snowflake(activity_payload["application_id"])
                if "application_id" in activity_payload
                else None
            )
            activity.details = activity_payload.get("details")
            activity.state = activity_payload.get("state")

            emoji = activity_payload.get("emoji")
            activity.emoji = self.deserialize_emoji(emoji) if emoji is not None else None

            party = None
            if "party" in activity_payload:
                party_payload = activity_payload["party"]
                party = presence_models.ActivityParty()
                party.id = party_payload.get("id")

                if "size" in party_payload:
                    current_size, max_size = party_payload["size"]
                    party.current_size = int(current_size)
                    party.max_size = int(max_size)
                else:
                    party.current_size = party.max_size = None
            activity.party = party

            assets = None
            if "assets" in activity_payload:
                assets_payload = activity_payload["assets"]
                assets = presence_models.ActivityAssets()
                assets.large_image = assets_payload.get("large_image")
                assets.large_text = assets_payload.get("large_text")
                assets.small_image = assets_payload.get("small_image")
                assets.small_text = assets_payload.get("small_text")
            activity.assets = assets

            secrets = None
            if "secrets" in activity_payload:
                secrets_payload = activity_payload["secrets"]
                secrets = presence_models.ActivitySecret()
                secrets.join = secrets_payload.get("join")
                secrets.spectate = secrets_payload.get("spectate")
                secrets.match = secrets_payload.get("match")
            activity.secrets = secrets

            activity.is_instance = activity_payload.get("instance")  # TODO: can we safely default this to False?
            # noinspection PyArgumentList
            activity.flags = (
                presence_models.ActivityFlag(activity_payload["flags"]) if "flags" in activity_payload else None
            )
            activities.append(activity)
        presence.activities = activities

        client_status_payload = payload["client_status"]
        client_status = presence_models.ClientStatus()
        # noinspection PyArgumentList
        client_status.desktop = (
            presence_models.Status(client_status_payload["desktop"])
            if "desktop" in client_status_payload
            else presence_models.Status.OFFLINE
        )
        # noinspection PyArgumentList
        client_status.mobile = (
            presence_models.Status(client_status_payload["mobile"])
            if "mobile" in client_status_payload
            else presence_models.Status.OFFLINE
        )
        # noinspection PyArgumentList
        client_status.web = (
            presence_models.Status(client_status_payload["web"])
            if "web" in client_status_payload
            else presence_models.Status.OFFLINE
        )
        presence.client_status = client_status

        # TODO: do we want to differentiate between undefined and null here?
        premium_since = payload.get("premium_since")
        presence.premium_since = (
            date.iso8601_datetime_string_to_datetime(premium_since) if premium_since is not None else None
        )

        # TODO: do we want to differentiate between undefined and null here?
        presence.nickname = payload.get("nick")
        return presence

    ###############
    # USER MODELS #
    ###############

    @staticmethod
    def _set_user_attributes(payload: data_binding.JSONObject, user: user_models.UserImpl) -> None:
        user.id = snowflake.Snowflake(payload["id"])
        user.discriminator = payload["discriminator"]
        user.username = payload["username"]
        user.avatar_hash = payload["avatar"]
        user.is_bot = payload.get("bot", False)
        user.is_system = payload.get("system", False)

    def deserialize_user(self, payload: data_binding.JSONObject) -> user_models.UserImpl:
        user = user_models.UserImpl()
        user.app = self._app
        self._set_user_attributes(payload, user)
        # noinspection PyArgumentList
        user.flags = (
            user_models.UserFlag(payload["public_flags"]) if "public_flags" in payload else user_models.UserFlag.NONE
        )
        return user

    def deserialize_my_user(self, payload: data_binding.JSONObject) -> user_models.OwnUser:
        my_user = user_models.OwnUser()
        my_user.app = self._app
        self._set_user_attributes(payload, my_user)
        my_user.is_mfa_enabled = payload["mfa_enabled"]
        my_user.locale = payload.get("locale")
        my_user.is_verified = payload.get("verified")
        my_user.email = payload.get("email")
        # noinspection PyArgumentList
        my_user.flags = user_models.UserFlag(payload["flags"])
        # noinspection PyArgumentList
        my_user.premium_type = user_models.PremiumType(payload["premium_type"]) if "premium_type" in payload else None
        return my_user

    ################
    # VOICE MODELS #
    ################

    def deserialize_voice_state(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflake.Snowflake] = undefined.UNDEFINED,
        member: undefined.UndefinedOr[guild_models.Member] = undefined.UNDEFINED,
    ) -> voice_models.VoiceState:
        voice_state = voice_models.VoiceState()
        voice_state.app = self._app
        voice_state.guild_id = snowflake.Snowflake(payload["guild_id"]) if guild_id is undefined.UNDEFINED else guild_id

        if (channel_id := payload["channel_id"]) is not None:
            channel_id = snowflake.Snowflake(channel_id)
        voice_state.channel_id = channel_id

        voice_state.user_id = snowflake.Snowflake(payload["user_id"])

        if member is undefined.UNDEFINED:
            voice_state.member = self.deserialize_member(payload["member"], guild_id=voice_state.guild_id)
        else:
            voice_state.member = member

        voice_state.session_id = payload["session_id"]
        voice_state.is_guild_deafened = payload["deaf"]
        voice_state.is_guild_muted = payload["mute"]
        voice_state.is_self_deafened = payload["self_deaf"]
        voice_state.is_self_muted = payload["self_mute"]
        voice_state.is_streaming = payload.get("self_stream", False)
        voice_state.is_video_enabled = payload["self_video"]
        voice_state.is_suppressed = payload["suppress"]
        return voice_state

    def deserialize_voice_region(self, payload: data_binding.JSONObject) -> voice_models.VoiceRegion:
        voice_region = voice_models.VoiceRegion()
        voice_region.id = payload["id"]
        voice_region.name = payload["name"]
        voice_region.is_vip = payload["vip"]
        voice_region.is_optimal_location = payload["optimal"]
        voice_region.is_deprecated = payload["deprecated"]
        voice_region.is_custom = payload["custom"]
        return voice_region

    ##################
    # WEBHOOK MODELS #
    ##################

    def deserialize_webhook(self, payload: data_binding.JSONObject) -> webhook_models.Webhook:
        webhook = webhook_models.Webhook()
        webhook.app = self._app
        webhook.id = snowflake.Snowflake(payload["id"])
        # noinspection PyArgumentList
        webhook.type = webhook_models.WebhookType(payload["type"])
        webhook.guild_id = snowflake.Snowflake(payload["guild_id"]) if "guild_id" in payload else None
        webhook.channel_id = snowflake.Snowflake(payload["channel_id"])
        webhook.author = self.deserialize_user(payload["user"]) if "user" in payload else None
        webhook.name = payload["name"]
        webhook.avatar_hash = payload["avatar"]
        webhook.token = payload.get("token")
        return webhook