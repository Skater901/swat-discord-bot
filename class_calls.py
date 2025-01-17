#!/usr/bin/python
import os
import re
from typing import Dict

from dotenv import load_dotenv
from discord.ext import commands
from discord.ext.tasks import loop

from class_call import ClassCall

cc_regex = '^(?P<position>[1-9])\s?[-]?\s?(?P<name>[^\d].*)$'

load_dotenv()
SWAT_SERVER_ID = os.getenv('SWAT_SERVER_ID')
SWAT_CC_CHANNEL_ID = os.getenv('SWAT_CC_CHANNEL_ID')
TEST_SERVER_ID = os.getenv('TEST_SERVER_ID')
SWAT_CC_CHANNEL = os.getenv('SWAT_CC_CHANNEL')
TEST_CC_CHANNEL = os.getenv('TEST_CC_CHANNEL')


class ClassCalls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.class_call = ClassCall()
        self.auto_lock_cc.start()

    @commands.command(name='cc', help='Responds with the current Class Call. If given a format as an argument, it will respond with the current Class Call in that format.')
    async def cc(self, ctx, format=None):
        self.class_call.time_since_last_call = 0
        if format:
            await ctx.send(self.class_call.export(format))
        else:
            await ctx.send(str(self.class_call))

    @commands.command(name='startcc', help='Starts the Class Call.')
    async def start_cc(self, ctx):
        self.class_call = ClassCall()
        await ctx.send('Class Call started')

    @commands.command(name='clearcc', help='Resets the Class Call.')
    async def clear_cc(self, ctx):
        self.class_call = ClassCall()
        await ctx.send('Class Call restarted')

    @commands.command(name='stopcc', help='Disables the Class Call')
    async def stop_cc(self, ctx):
        self.class_call = None
        await ctx.send('Class Call stopped')

    @commands.command(name='set_format', help='Set format the Class Call is output in. Possible formats: default, grid')
    async def set_format(self, ctx, format):
        self.class_call.time_since_last_call = 0
        error_message = self.class_call.set_format(format)
        await ctx.send(error_message or 'Set format to {}'.format(format))

    @commands.command(name='import_cc',
                      help='Imports a Class Call. Only supports the default format. Multiple blank space characters are squashed into one.')
    async def import_cc(self, ctx, *cc):
        if not self.class_call:
            await ctx.send('Class Call started')
            self.class_call = ClassCall()
        success = self.class_call.import_cc(' '.join(cc))
        if success:
            await ctx.send('Class Call imported')
            await ctx.send(str(self.class_call))
        else:
            await ctx.send('Invalid format, preserving original Class Call')

    @commands.command(name='close',
                      help='Close all slots listed by marking the call with a "-". Slots are listed by number, separated by spaces.')
    async def close(self, ctx, *slots):
        for slot in slots:
            call = '{} --'.format(slot)
            print(call)
            cc_match = re.match(cc_regex, call)
            self.class_call.receive_call(ctx.message.author.name, cc_match)
        await ctx.send('Closed slots {}'.format(" ".join(slots)))
        await ctx.send(str(self.class_call))

    @commands.command(name='mode', help='Set the mode. Accepts a string representing the mode declared.')
    async def mode(self, ctx, input=None):
        self.class_call.time_since_last_call = 0
        if input:
            self.class_call.mode = input
            await ctx.send('Mode set to {}'.format(self.class_call.mode))
        else:
            await ctx.send('Mode currently set to {}'.format(self.class_call.mode))

    @commands.command(name='leader', help='Set the leader. Accepts a string representing the leader declared.')
    async def leader(self, ctx, input=None):
        self.class_call.time_since_last_call = 0
        if input:
            self.class_call.leader = input
            await ctx.send('Leader set to {}'.format(self.class_call.leader))
        else:
            await ctx.send('Leader currently set to {}'.format(self.class_call.leader))

    @commands.command(name='lock', help='Locks the class call, so no more calls can be made.')
    async def lock(self, ctx):
        self.class_call.time_since_last_call = 0
        self.class_call.lock = True
        await ctx.send('Class call locked.')

    @commands.command(name='unlock', help='Unlocks the class call, so calls can be made.')
    async def unlock(self, ctx):
        self.class_call.time_since_last_call = 0
        self.class_call.lock = False
        await ctx.send('Class call unlocked.')

    @commands.command(name='set_lock_timer',
                      help='Sets the inactivity period until the class call is automatically locked, in seconds.')
    async def set_lock_timer(self, ctx, input=None):
        if input:
            self.class_call.lock_timer = int(input)
            await ctx.send('Lock timer set to {}'.format(self.class_call.lock_timer))
        else:
            await ctx.send('Lock timer currently set to {}'.format(self.class_call.lock_timer))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if not ((message.channel.name == TEST_CC_CHANNEL and str(message.guild.id) == TEST_SERVER_ID) or
                (message.channel.name == SWAT_CC_CHANNEL and str(message.guild.id) == SWAT_SERVER_ID)):
            return

        cc_match = re.match(cc_regex, message.content)
        if cc_match:
            if not self.class_call.lock:
                if not self.class_call:
                    await message.channel.send('Class Call started')
                    self.class_call = ClassCall()
                    self.class_call.lock = False
                self.class_call.receive_call(message.author.name, cc_match)
                await message.channel.send(str(self.class_call))
            else:
                await message.channel.send('Class Call locked.')

    @loop(seconds=1)
    async def auto_lock_cc(self):
        await self.bot.wait_until_ready()
        if self.class_call:
            self.class_call.time_since_last_call += 1
            if ((self.class_call.time_since_last_call >= self.class_call.lock_timer) and
                    self.class_call.class_call_used and
                    not self.class_call.lock):
                self.class_call.lock = True
                channel = self.bot.get_channel(int(SWAT_CC_CHANNEL_ID))
                # await channel.send('Class Call locked after {} seconds of inactivity.'.format(self.class_call.lock_timer))

    @commands.command(name='swap', help='Swaps the position of two classes in the class call. Example, !swap 1 9')
    async def swap(self, ctx, *slots: str):
        if (len(slots)) != 2:
            return

        if (not self.__validate_swap_slot(slots[0])) or (not self.__validate_swap_slot(slots[1])):
            return

        if self.class_call.lock:
            await ctx.send('Class Call locked.')
            return

        first_slot = slots[0]

        second_slot = slots[1]

        self.__swap(first_slot, second_slot)

        self.__swap(second_slot, first_slot)

        self.class_call.data.sort(key=lambda x: x['position'])

        await ctx.send('Swapped slots {} and {}'.format(first_slot, second_slot))
        await ctx.send(str(self.class_call))

    @staticmethod
    def __validate_swap_slot(slot: str) -> bool:
        try:
            slot_number = int(slot)
            return 0 < slot_number < 10
        except ValueError:
            return False

    def __find_position(self, position: str) -> Dict[str, str]:
        return next(filter(lambda x: x['position'] == position, self.class_call.data), None)

    def __swap(self, current: str, new: str):
        call: Dict[str, str] = self.__find_position(current)

        if call is not None:
            call['position'] = new
