import asyncio

from types import MappingProxyType
from collections import namedtuple
from modules import database
from modules import UserLevel


Handler = namedtuple('Handler', ('coroutine', 'user_level', 'description'))


class CommandDispatcher:
    def __init__(self, bot, command):
        self._bot = bot
        self._command = command
        self._child_dispatchers = {}
        self._handlers = []

    @property
    def command(self):
        return self._command

    @property
    def handlers(self):
        return list(self._handlers)

    @property
    def child_dispatchers(self):
        return MappingProxyType(self._child_dispatchers)

    @property
    def user_level(self):
        levels = []

        if self._handlers:
            levels += [h.user_level for h in self._handlers]

        if self._child_dispatchers:
            levels += [c.user_level for c in self._child_dispatchers.values()]

        levels = filter(None.__ne__, levels)

        return min(levels) if levels else None

    @property
    def is_leaf(self):
        return not self._child_dispatchers

    def ensure_child_dispatchers(self, commands):
        command, sub_commands = (commands.split(' ', 1) + [''])[:2]
        dispatcher = self._ensure_child_dispatcher(command)

        if sub_commands:
            return dispatcher.ensure_child_dispatchers(sub_commands)

        return dispatcher

    def _ensure_child_dispatcher(self, command):
        if command not in self._child_dispatchers:
            dispatcher = self.__class__(self._bot, command)
            self._child_dispatchers[command] = dispatcher

        return self._child_dispatchers[command]

    def register_handler(self, handler, command=None):
        if not command:
            self._handlers.append(handler)
            return self

        return self.ensure_child_dispatchers(command).register_handler(handler)

    def get(self, command_text, user_level):
        command, sub_commands = (command_text.split(' ', 1) + [''])[:2]
        command = self._get_command_from_alias(command)

        try:
            dispatcher = self._child_dispatchers[command]
            if dispatcher.user_level <= user_level:
                return dispatcher.get(sub_commands, user_level)

        except KeyError:
            pass

        return (self, command_text)

    def _get_command_from_alias(self, command):
        alias = database.get_CommandAlias_by_alias(command)
        return alias.command if alias else command

    def dispatch(self, command, message):
        user_level = UserLevel.get(message.author, message.channel)
        dispatcher, attributes = self.get(command, user_level)
        handlers = [h for h in dispatcher.handlers if h.user_level <= user_level]

        for handler in handlers:
            asyncio.ensure_future(self._wrapper(
                handler.coroutine,
                attributes,
                message
            ))

        return bool(handlers)

    async def _wrapper(self, coroutine, attributes, message):
        try:
            await coroutine(attributes, message)

        except CommandException as ex:
            await self._bot.send_message(message.channel, str(ex))


class CommandException(Exception):
    pass
