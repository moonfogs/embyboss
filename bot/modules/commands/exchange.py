"""
兑换注册码exchange
"""
from datetime import timedelta, datetime

from bot import bot, _open, LOGGER, bot_photo, user_buy
from bot.func_helper.emby import emby
from bot.func_helper.fix_bottons import register_code_ikb
from bot.func_helper.msg_utils import sendMessage, sendPhoto
from bot.sql_helper.sql_code import Code
from bot.sql_helper.sql_emby import sql_get_emby, Emby
from bot.sql_helper import Session


async def rgs_code(_, msg, register_code):
    if _open.stat: return await sendMessage(msg, "🤧 自由注册开启下无法使用注册码。")

    data = sql_get_emby(tg=msg.from_user.id)
    if not data: return await sendMessage(msg, "出错了，不确定您是否有资格使用，请先 /start")
    embyid = data.embyid
    ex = data.ex
    lv = data.lv
    if embyid:
        if not _open.allow_code: return await sendMessage(msg,
                                                          "🔔 很遗憾，管理员已经将注册码续期关闭\n**已有账户成员**无法使用register_code，请悉知",
                                                          timer=60)
        with Session() as session:
            # with_for_update 是一个排他锁，其实就不需要悲观锁或者是乐观锁，先锁定先到的数据使其他session无法读取，修改(单独似乎不起作用，也许是不能完全防止并发冲突，于是加入原子操作)
            r = session.query(Code).filter(Code.code == register_code).with_for_update().first()
            if not r: return await sendMessage(msg, "⛔ **你输入了一个错误de注册码，请确认好重试。**", timer=60)
            re = session.query(Code).filter(Code.code == register_code, Code.used.is_(None)).with_for_update().update(
                {Code.used: msg.from_user.id, Code.usedtime: datetime.now()})
            session.commit()  # 必要的提交。否则失效
            tg1 = r.tg
            us1 = r.us
            used = r.used
            if re == 0: return await sendMessage(msg,
                                                 f'此 `{register_code}` \n注册码已被使用,是[{used}](tg://user?id={used})的形状了喔')
            session.query(Code).filter(Code.code == register_code).with_for_update().update(
                {Code.used: msg.from_user.id, Code.usedtime: datetime.now()})
            first = await bot.get_chat(tg1)
            # 此处需要写一个判断 now和ex的大小比较。进行日期加减。
            ex_new = datetime.now()
            if ex_new > ex:
                ex_new = ex_new + timedelta(days=us1)
                await emby.emby_change_policy(id=embyid, method=False)
                if lv == 'c':
                    session.query(Emby).filter(Emby.tg == msg.from_user.id).update({Emby.ex: ex_new, Emby.lv: 'b'})
                else:
                    session.query(Emby).filter(Emby.tg == msg.from_user.id).update({Emby.ex: ex_new})
                await sendMessage(msg, f'🎊 少年郎，恭喜你，已收到 [{first.first_name}](tg://user?id={tg1}) 的{us1}天🎁\n'
                                       f'__已解封账户并延长到期时间至(以当前时间计)__\n到期时间：{ex_new.strftime("%Y-%m-%d %H:%M:%S")}')
            elif ex_new < ex:
                ex_new = data.ex + timedelta(days=us1)
                session.query(Emby).filter(Emby.tg == msg.from_user.id).update({Emby.ex: ex_new})
                await sendMessage(msg,
                                  f'🎊 少年郎，恭喜你，已收到 [{first.first_name}](tg://user?id={tg1}) 的{us1}天🎁\n到期时间：{ex_new}__')
            session.commit()
            new_code = register_code[:-7] + "░" * 7
            await sendMessage(msg,
                                  f'· 🎟️ 续期码使用 - [{msg.from_user.first_name}](tg://user?id={msg.chat.id}) [{msg.from_user.id}] 使用了 {new_code}\n· 📅 实时到期 - {ex_new}',
                                  send=True)
            LOGGER.info(f"【续期码】：{msg.from_user.first_name}[{msg.chat.id}] 使用了 {register_code}，到期时间：{ex_new}")

    else:
        with Session() as session:
            # 我勒个豆，终于用 原子操作 + 排他锁 成功防止了并发更新
            # 在 UPDATE 语句中添加一个条件，只有当注册码未被使用时，才更新数据。这样，如果有两个用户同时尝试使用同一条注册码，只有一个用户的 UPDATE 语句会成功，因为另一个用户的 UPDATE 语句会发现注册码已经被使用。
            r = session.query(Code).filter(Code.code == register_code).with_for_update().first()
            if not r: return await sendMessage(msg, "⛔ **你输入了一个错误de注册码，请确认好重试。**")
            re = session.query(Code).filter(Code.code == register_code, Code.used.is_(None)).with_for_update().update(
                {Code.used: msg.from_user.id, Code.usedtime: datetime.now()})
            session.commit()  # 必要的提交。否则失效
            tg1 = r.tg
            us1 = r.us
            used = r.used
            if re == 0: return await sendMessage(msg,
                                                 f'此 `{register_code}` \n注册码已被使用,是 [{used}](tg://user?id={used}) 的形状了喔')
            first = await bot.get_chat(tg1)
            x = data.us + us1
            session.query(Emby).filter(Emby.tg == msg.from_user.id).update({Emby.us: x})
            session.commit()
            await sendPhoto(msg, photo=bot_photo,
                            caption=f'🎊 少年郎，恭喜你，已经收到了 [{first.first_name}](tg://user?id={tg1}) 发送的邀请注册资格\n\n请选择你的选项~',
                            buttons=register_code_ikb)
            new_code = register_code[:-7] + "░" * 7
            await sendMessage(msg,
                                  f'· 🎟️ 注册码使用 - [{msg.from_user.first_name}](tg://user?id={msg.chat.id}) [{msg.from_user.id}] 使用了 {new_code} 可以创建{us1}天账户咯~',
                                  send=True)
            LOGGER.info(
                f"【注册码】：{msg.from_user.first_name}[{msg.chat.id}] 使用了 {register_code} - 可创建 {us1}天账户")


# @bot.on_message(filters.regex('exchange') & filters.private & user_in_group_on_filter)
# async def exchange_buttons(_, call):
#
#     await rgs_code(_, msg)
