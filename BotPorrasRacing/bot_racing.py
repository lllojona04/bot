import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime
import re

# ====== CONFIGURACIÓN ======
TOKEN = "TU_TOKEN_AQUI"  # 👈 Pega aquí tu token real
CANALES_PORRA = ["porra-actual"]  # Nombre base del canal de porras
CANALES_CLASIFICACION = ["clasificación"]  # Nombre base del canal de ranking

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== ARCHIVO DE DATOS ======
if not os.path.exists("porras.json"):
    with open("porras.json", "w") as f:
        json.dump({"porras": {}, "puntos": {}, "proximo_partido": {}}, f)

def cargar_datos():
    with open("porras.json", "r") as f:
        return json.load(f)

def guardar_datos(data):
    with open("porras.json", "w") as f:
        json.dump(data, f, indent=4)

# ====== EVENTO DE INICIO ======
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.Game(name="⚽ ¡Vamos Racing!"))
    publicar_recordatorio.start()
    publicar_top3.start()

# ====== FUNCIÓN PARA ENCONTRAR CANALES POR NOMBRE BASE ======
def buscar_canal(guild, nombres_base):
    for canal in guild.text_channels:
        canal_limpio = re.sub(r'[^a-zA-Z0-9]', '', canal.name).lower()
        for nombre in nombres_base:
            nombre_limpio = re.sub(r'[^a-zA-Z0-9]', '', nombre).lower()
            if nombre_limpio in canal_limpio:
                return canal
    return None

# ====== !nuevaporra ======
@bot.command(name="nuevaporra")
@commands.has_permissions(manage_messages=True)
async def nuevaporra(ctx, equipo_local: str, equipo_visitante: str, fecha: str):
    data = cargar_datos()
    partido = f"{equipo_local}-{equipo_visitante}"

    data["proximo_partido"] = {
        "local": equipo_local,
        "visitante": equipo_visitante,
        "fecha": fecha,
        "creado": str(datetime.now())
    }

    if partido not in data["porras"]:
        data["porras"][partido] = {"predicciones": {}}

    guardar_datos(data)

    canal_porra = buscar_canal(ctx.guild, CANALES_PORRA)
    if canal_porra:
        embed = discord.Embed(
            title="🆕 ¡Nueva Porra Abierta!",
            description=(
                f"**Partido:** {equipo_local} 🆚 {equipo_visitante}\n"
                f"**Fecha:** {fecha}\n\n"
                f"Usa el comando:\n`!porra {equipo_local} X-Y {equipo_visitante}`\n\n"
                f"Por ejemplo: `!porra {equipo_local} 2-1 {equipo_visitante}`"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Bot de Porras del Racing • ¡Vamos Racing!")
        await canal_porra.send(embed=embed)
        await ctx.send(f"✅ Porra creada y anunciada en #{canal_porra.name}")
    else:
        await ctx.send("⚠️ No encontré el canal de porras.")

# ====== !porra ======
@bot.command(name="porra")
async def porra(ctx, equipo_local: str, resultado: str, equipo_visitante: str):
    canal_permitido = buscar_canal(ctx.guild, CANALES_PORRA)
    if not canal_permitido or ctx.channel.id != canal_permitido.id:
        await ctx.send(f"❌ Este comando solo se puede usar en un canal de porras.")
        return

    data = cargar_datos()
    partido = f"{equipo_local}-{equipo_visitante}"
    autor = str(ctx.author.id)

    if partido not in data["porras"]:
        await ctx.send("⚠️ No hay una porra activa para ese partido.")
        return

    if autor in data["porras"][partido]["predicciones"]:
        await ctx.send(f"⚠️ {ctx.author.display_name}, ya has hecho tu apuesta para este partido.")
        return

    data["porras"][partido]["predicciones"][autor] = resultado
    guardar_datos(data)

    embed = discord.Embed(
        title="✅ Apuesta Registrada",
        description=f"**{ctx.author.display_name}** apostó `{resultado}` en **{equipo_local} vs {equipo_visitante}**.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# ====== !resultado ======
@bot.command(name="resultado")
@commands.has_permissions(manage_messages=True)
async def resultado(ctx, equipo_local: str, resultado_real: str, equipo_visitante: str):
    canal_permitido = buscar_canal(ctx.guild, CANALES_PORRA)
    if not canal_permitido or ctx.channel.id != canal_permitido.id:
        await ctx.send(f"❌ Este comando solo se puede usar en un canal de porras.")
        return

    data = cargar_datos()
    partido = f"{equipo_local}-{equipo_visitante}"

    if partido not in data["porras"]:
        await ctx.send("⚠️ No hay apuestas registradas para ese partido.")
        return

    try:
        real_gf, real_gc = map(int, resultado_real.split("-"))
    except ValueError:
        await ctx.send("⚠️ Formato de resultado incorrecto. Usa `GolesLocal-GolesVisitante` (Ej: 2-1).")
        return

    apuestas = data["porras"][partido]["predicciones"]
    data.setdefault("puntos", {})
    resumen_puntos = []

    for user_id, pred in apuestas.items():
        try:
            pred_gf, pred_gc = map(int, pred.split("-"))
        except ValueError:
            continue
        puntos = 0
        if pred == resultado_real:
            puntos = 3
        elif (real_gf > real_gc and pred_gf > pred_gc) or (real_gf < real_gc and pred_gf < pred_gc) or (real_gf == real_gc and pred_gf == pred_gc):
            puntos = 1

        data["puntos"][user_id] = data["puntos"].get(user_id, 0) + puntos
        user = await bot.fetch_user(int(user_id))
        resumen_puntos.append(f"🏅 **{user.display_name}** → +{puntos} puntos ({pred})")

    guardar_datos(data)

    embed = discord.Embed(
        title=f"🏁 Resultado Final: {equipo_local} {resultado_real} {equipo_visitante}",
        description="\n".join(resumen_puntos),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Sistema de Puntos: 3 Exacto | 1 Resultado | 0 Fallo")
    await ctx.send(embed=embed)

# ====== !ranking ======
@bot.command(name="ranking")
async def ranking(ctx):
    canal_permitido = buscar_canal(ctx.guild, CANALES_CLASIFICACION)
    if not canal_permitido or ctx.channel.id != canal_permitido.id:
        await ctx.send(f"❌ Este comando solo se puede usar en un canal de clasificación.")
        return

    data = cargar_datos()
    puntos = data.get("puntos", {})

    if not puntos:
        await ctx.send("😅 Aún no hay puntos registrados.")
        return

    ranking_ordenado = sorted(puntos.items(), key=lambda x: x[1], reverse=True)
    msg = ""
    for i, (user_id, pts) in enumerate(ranking_ordenado, start=1):
        user = await bot.fetch_user(int(user_id))
        msg += f"**{i}.** {user.display_name} — {pts} pts\n"

    embed = discord.Embed(
        title="📊 Clasificación General",
        description=msg,
        color=discord.Color.blue()
    )
    embed.set_footer(text="Actualizado automáticamente por el Bot de Porras del Racing")
    await ctx.send(embed=embed)

# ====== !borrarporra ======
@bot.command(name="borrarporra")
async def borrarporra(ctx, equipo_local: str, equipo_visitante: str):
    canal_permitido = buscar_canal(ctx.guild, CANALES_PORRA)
    if not canal_permitido or ctx.channel.id != canal_permitido.id:
        await ctx.send("❌ Este comando solo se puede usar en un canal de porras.")
        return

    data = cargar_datos()
    partido = f"{equipo_local}-{equipo_visitante}"
    autor = str(ctx.author.id)

    if partido not in data["porras"]:
        await ctx.send("⚠️ No hay una porra activa para este partido.")
        return

    if autor not in data["porras"][partido]["predicciones"]:
        await ctx.send("⚠️ No tienes ninguna apuesta registrada para este partido.")
        return

    del data["porras"][partido]["predicciones"][autor]
    guardar_datos(data)
    await ctx.send(f"✅ {ctx.author.display_name}, tu apuesta para **{equipo_local} vs {equipo_visitante}** ha sido eliminada. Ahora puedes volver a apostar con `!porra`.")

# ====== !cerrarporra ======
@bot.command(name="cerrarporra")
@commands.has_permissions(manage_messages=True)
async def cerrarporra(ctx, equipo_local: str, equipo_visitante: str):
    canal_permitido = buscar_canal(ctx.guild, CANALES_PORRA)
    if not canal_permitido or ctx.channel.id != canal_permitido.id:
        await ctx.send("❌ Este comando solo se puede usar en un canal de porras.")
        return

    data = cargar_datos()
    partido = f"{equipo_local}-{equipo_visitante}"

    if partido not in data["porras"]:
        await ctx.send("⚠️ No hay una porra activa para este partido.")
        return

    del data["porras"][partido]
    if data.get("proximo_partido") and data["proximo_partido"]["local"] == equipo_local and data["proximo_partido"]["visitante"] == equipo_visitante:
        data["proximo_partido"] = {}

    guardar_datos(data)
    await ctx.send(f"✅ La porra de **{equipo_local} vs {equipo_visitante}** ha sido cerrada y eliminada.")

# ====== RECORDATORIOS Y TOP 3 ======
@tasks.loop(hours=24)
async def publicar_recordatorio():
    data = cargar_datos()
    if not data.get("proximo_partido"):
        return

    fecha = data["proximo_partido"]["fecha"]
    local = data["proximo_partido"]["local"]
    visitante = data["proximo_partido"]["visitante"]

    hoy = datetime.now().strftime("%d/%m/%Y")
    if fecha == hoy:
        for guild in bot.guilds:
            canal_porra = buscar_canal(guild, CANALES_PORRA)
            if canal_porra:
                await canal_porra.send(
                    f"🏟️ ¡Hoy juega el **{local}** contra **{visitante}**!\n"
                    f"Última oportunidad para apostar con `!porra {local} X-Y {visitante}` ⚽"
                )

@tasks.loop(hours=24)
async def publicar_top3():
    ahora = datetime.now()
    if ahora.weekday() == 0 and ahora.hour == 10:
        for guild in bot.guilds:
            canal = buscar_canal(guild, CANALES_CLASIFICACION)
            if canal:
                data = cargar_datos()
                puntos = data.get("puntos", {})
                if not puntos:
                    continue

                ranking_ordenado = sorted(puntos.items(), key=lambda x: x[1], reverse=True)
                top3 = ranking_ordenado[:3]
                msg = ""
                medallas = ["🥇", "🥈", "🥉"]

                for i, (user_id, pts) in enumerate(top3):
                    user = await bot.fetch_user(int(user_id))
                    msg += f"{medallas[i]} {user.mention} — {pts} pts\n"

                fecha = datetime.now().strftime("%d/%m/%Y")
                embed = discord.Embed(
                    title=f"🏆 Top 3 de la Semana ({fecha})",
                    description=msg + "\n¡Sigue participando en la porra actual!",
                    color=discord.Color.purple()
                )
                embed.set_footer(text="Bot de Porras del Racing • Clasificación semanal")
                await canal.send(embed=embed)

# ====== ERRORES ======
@porra.error
async def porra_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Uso correcto: `!porra <EquipoLocal> <Marcador> <EquipoVisitante>`")

@resultado.error
async def resultado_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Uso correcto: `!resultado <EquipoLocal> <MarcadorFinal> <EquipoVisitante>`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 Solo administradores/moderadores pueden usar este comando.")

@nuevaporra.error
async def nueva_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Uso correcto: `!nuevaporra <EquipoLocal> <EquipoVisitante> <Fecha(dd/mm/aaaa)>`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 Solo administradores/moderadores pueden crear nuevas porras.")

@ranking.error
async def ranking_error(ctx, error):
    await ctx.send("⚠️ Solo se puede usar en el canal de clasificación correcto.")















