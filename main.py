"""
Punto de entrada del nodo.

Uso:
  # Primer nodo (sin peers)
  python main.py --port 7000

  # Segundo nodo conectado al primero
  python main.py --port 7001 --peers localhost:7000

  # Mandar un prompt desde otro terminal
  python main.py --port 7002 --peers localhost:7000,localhost:7001 --prompt "¿Qué es la fotosíntesis?"

  # Ver identidad y puntos de un nodo
  python main.py --port 7000 --status
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from node import Nodo
from data_pool import DataPool
import identity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def parsear_peers(peers_str: str) -> list[tuple[str, int]]:
    if not peers_str:
        return []
    resultado = []
    for p in peers_str.split(","):
        host, port = p.strip().split(":")
        resultado.append((host, int(port)))
    return resultado


async def main():
    parser = argparse.ArgumentParser(description="Nodo de la red IA descentralizada")
    parser.add_argument("--host",        default="0.0.0.0")
    parser.add_argument("--port",        type=int, required=True)
    parser.add_argument("--peers",       default="")
    parser.add_argument("--prompt",      default="")
    parser.add_argument("--status",      action="store_true")
    parser.add_argument("--public-host", default="", help="IP pública para anunciarse (auto-detecta si no se especifica)")
    args = parser.parse_args()

    peers = parsear_peers(args.peers)

    # Modo status: muestra identidad y puntos sin arrancar el nodo
    if args.status:
        id_data = identity.cargar_o_crear(args.port)
        ledger_path = identity.ruta_ledger(args.port)
        puntos = {}
        if ledger_path.exists():
            with open(ledger_path) as f:
                puntos = json.load(f)
        print(f"""
╔══════════════════════════════════════╗
║     Identidad del Nodo               ║
╚══════════════════════════════════════╝
  Node ID  : {id_data['node_id']}
  Puerto   : {args.port}
  Creado   : {id_data['creado']}
  Identidad: ~/.red_ia/{args.port}/identity.json

  Puntos en el ledger:
  {json.dumps(puntos, indent=4) if puntos else '  (sin puntos todavía)'}
""")
        pool  = DataPool(Path.home() / ".red_ia" / str(args.port))
        stats = pool.stats()
        print(f"""  Pool de datos:
    Total conversaciones : {stats['total']}
    Aprobadas            : {stats['aprobadas']}
    Pendientes           : {stats['pendientes']}
    Rechazadas           : {stats['rechazadas']}
    Listas para training : {stats['training_size']}
""")
        return

    # Auto-detectar IP pública para anunciarse correctamente
    public_host = args.public_host
    if not public_host:
        try:
            import urllib.request
            public_host = urllib.request.urlopen("https://ifconfig.me", timeout=5).read().decode().strip()
        except Exception:
            public_host = args.host

    nodo = Nodo(host=args.host, port=args.port, peers_iniciales=peers, public_host=public_host)

    # Modo prompt: conecta, manda el prompt, imprime resultado y sale
    if args.prompt:
        await nodo._servidor.iniciar()
        from network import conectar
        for h, p in peers:
            # Intentar como seed primero para descubrir peers reales
            peers_descubiertos = await nodo._conectar_seed(h, p)
            if peers_descubiertos:
                for pd in peers_descubiertos:
                    peer = await conectar(pd["host"], pd["port"], nodo._on_message)
                    if peer:
                        await nodo._saludar(peer)
            else:
                peer = await conectar(h, p, nodo._on_message)
                if peer:
                    await nodo._saludar(peer)

        await asyncio.sleep(1)
        print(f"\nEnviando prompt a la red...\n")
        respuesta = await nodo.coordinar_prompt(args.prompt)
        print(f"\nRespuesta:\n{respuesta}" if respuesta else "\nSin respuesta de la red.")
        return

    # Modo nodo: arranca y corre indefinidamente
    estado = "NUEVO  — primera vez en la red" if nodo._es_nuevo else "CONOCIDO — identidad restaurada"
    print(f"""
╔══════════════════════════════════════╗
║     Red IA Descentralizada           ║
╚══════════════════════════════════════╝
  Node ID  : {nodo.node_id}
  Puerto   : {args.port}
  Estado   : {estado}
  Peers    : {peers or 'ninguno (primer nodo)'}
  Datos    : ~/.red_ia/{args.port}/

  Esperando conexiones...
""")
    await nodo.arrancar()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nNodo detenido.")
