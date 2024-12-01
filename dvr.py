#!/usr/bin/env python
"""
Semplice implementazione del protocollo Distance Vector Routing su una rete di router simulata.
Per maggiori informazioni vedere report.pdf.

Richiede Python 3.9+

Marco Buda, 2024
marco.buda3@studio.unibo.it - 0001071464
"""

from typing import TypeAlias
import itertools
from threading import Thread, Lock, Condition
import time

# Il DV associa ai nodi l'attuale stima del percorso più breve
# In particolare ne memorizza il costo e il next hop
# Quest'ultimo può essere omesso nei percorsi da un nodo a se stesso
DistanceVector: TypeAlias = dict[str, tuple[int, str | None]]

# Una versione semplificata del datagramma IP
# Contiene solamente il nome del router sorgente e un DV come payload
Datagram: TypeAlias = tuple[str, 'DistanceVector']

# Rappresenta un collegamento unidirezionale tra due router
# Per una connessione full-duplex (che nella realtà sarebbe un unico cavo) servono due link
class Link:
    _cost: int
    _destination: 'Router'

    def __init__(self, cost: int, destination: 'Router'):
        self._cost = cost
        self._destination = destination

    # Simula il processo di scoperta del router collegato e misura del costo del collegamento
    def get_info(self):
        return (self._cost, self._destination._name)

    def send(self, data: 'Datagram'):
        Thread(daemon = False, target = self._send, args = (data,)).start()

    def _send(self, data: 'Datagram'):
        time.sleep(self._cost)
        self._destination.receive(data)

class Router:
    _name: str
    _links: list['Link']    # Contiene tutti i collegamenti in uscita dal router
    _dv: 'DistanceVector'
    _dv_cond: 'Condition'   # Regola l'accesso concorrente al DV

    def __init__(self, name: str):
        self._name = name
        self._links = []
        self._dv = dict()
        self._dv_cond = Condition()

    def connect(self, link: 'Link'):
        self._links.append(link)

    # Avvia le procedure del protocollo DVR
    def dvr_start(self):
        with self._dv_cond:
            # Inizializzo il DV con il percorso verso me stesso
            self._dv[self._name] = (0, None)
            log_dv(self._name, self._dv)
            # Scopro i nodi vicini
            self._find_neighbors()
            # Invio a tutti il mio DV aggiornato
            self._broadcast_dv()
            # Risveglio eventuali thread che stessero aspettando l'inizializzazione
            self._dv_cond.notify_all()

    # I dettagli del processo di scoperta dei nodi vicini sono omessi
    def _find_neighbors(self):
        for link in self._links:
            cost, neighbor_name = link.get_info()
            self._dv[neighbor_name] = (cost, neighbor_name)

    def _broadcast_dv(self):
        for link in self._links:
            link.send((self._name, self._dv))

    # Viene invocato quando un nodo vicino mi invia il suo DV
    def receive(self, data: 'Datagram'):
        with self._dv_cond:
            # Mi assicuro di attendere la fine della sequenza di inizializzazione
            while self._name not in self._dv:
                self._dv_cond.wait()

            sender, received_dv = data
            link_cost = self._dv[sender][0] # Rappresenta il costo del collegamento con il vicino
            changed = False
            # Esamino tutte le voci del DV che mi è stato inviato
            for node_name, (cost, next_hop) in received_dv.items():
                # Se trovo un percorso verso un nodo che non conoscevo
                # oppure trovo un percorso con costo minore della mia stima attuale
                # aggiorno il mio DV
                if node_name not in self._dv or link_cost + cost < self._dv[node_name][0]:
                    self._dv[node_name] = (link_cost + cost, sender)
                    changed = True
            # Se il mio DV è stato modificato lo inoltro ai nodi vicini
            if changed:
                log_dv(self._name, self._dv)
                self._broadcast_dv()

# Rappresenta un insieme di router collegati fra loro
class Network:
    _nodes: list['Router']

    # node_names:   I nomi dei router della rete
    # costs:        I costi dei collegamenti fra i router, oppure None quando non sono collegati
    #               Devono essere riportati in ordine lessicografico (vedere esempi sotto)
    def __init__(self, node_names: list[str], costs: list[int | None]):
        self._nodes = [Router(name) for name in node_names]
        for (a, b), cost in zip(itertools.combinations(self._nodes, 2), costs):
            if cost:
                Network._connect(a, b, cost)

    # Crea i collegamenti fra i due router specificati
    def _connect(a: 'Router', b: 'Router', cost: int):
        a.connect(Link(cost, b))
        b.connect(Link(cost, a))

    # Avvia le procedure del protocollo DVR su tutti i nodi della rete
    def dvr_start(self):
        for node in self._nodes:
            node.dvr_start()

console_lock = Lock() # Regola l'utilizzo concorrete dello standard output

# Stampa il DV di un router
def log_dv(source_name: str, dv: 'DistanceVector'):
    with console_lock:
        print(f"DV of router {source_name}:")
        for node_name, (cost, next_hop) in dv.items():
            print(f"Node: {node_name}, Cost: {cost}, Next hop: {next_hop}")
        print()

"""
Rete a pagina 21 del file 2_Routing_new.pdf:
    +---+---+---+---+
    | B | C | D | E |
+---+---+---+---+---+
| A | 1 | 6 | - | - |
+---+---+---+---+---+
| B |   | 2 | 1 | - |
+---+   +---+---+---+
| C |       | 3 | 7 |
+---+       +---+---+
| D |           | 2 |
+---+-----------+---+
"""
Network(
    ['A', 'B', 'C', 'D', 'E'],
    [1, 6, None, None, 2, 1, None, 3, 7, 2]
).dvr_start()

"""
Rete a pagina 22 del file 2_Routing_new.pdf:
    +---+---+---+---+---+
    | B | C | D | E | F |
+---+---+---+---+---+---+
| A | 1 | - | - | - | 3 |
+---+---+---+---+---+---+
| B |   | 3 | - | 5 | 1 |
+---+   +---+---+---+---+
| C |       | 2 | - | - |
+---+       +---+---+---+
| D |           | 1 | 6 |
+---+           +---+---+
| E |               | 2 |
+---+---------------+---+
"""
# Network(
#     ['A', 'B', 'C', 'D', 'E', 'F'],
#     [1, None, None, None, 3, 3, None, 5, 1, 2, None, None, 1, 6, 2]
# ).dvr_start()
