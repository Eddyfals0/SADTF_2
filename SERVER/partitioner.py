"""
Partitioner: lógica modular para decidir colocación de bloques (primarios + réplicas)

La clase no persiste cambios; solo calcula asignaciones (placements) basadas en
la información de nodos y la tabla RAW de bloques (`blocks_store`), la cual debe
ser proporcionada por el coordinador/blocks_manager.

Algoritmo principal: round-robin sobre nodos ONLINE que tengan bloques libres,
asignando para cada bloque un 'primary' y N-1 réplicas en nodos distintos.
"""
from typing import List, Dict, Any, Tuple


class Partitioner:
    def __init__(self, replication: int = 2):
        if replication < 1:
            raise ValueError("replication must be >= 1")
        self.replication = replication

    def _online_nodes(self, nodos_registrados: Dict[str, Any]) -> List[str]:
        return [nid for nid, info in nodos_registrados.items() if info.get('status') == 'online']

    def _free_blocks_by_node(self, blocks_raw: Dict[str, Any]) -> Dict[str, List[str]]:
        """Devuelve mapping node_id -> lista de block_ids libres"""
        res = {}
        for bid, b in blocks_raw.get('blocks', {}).items():
            if b.get('status') == 'free':
                node = b.get('node')
                res.setdefault(node, []).append(bid)
        return res

    def allocate_blocks_for_file(self, num_blocks: int, nodos_registrados: Dict[str, Any], blocks_raw: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Calcula las asignaciones para `num_blocks` bloques del archivo.

        Retorna: (ok: bool, placements: list, message: str)
        Cada placement es: {
            'file_block_index': i (1-based),
            'primary_block_id': 'N1xxx', 'primary_node': 'nodo1',
            'replica_block_ids': [...], 'replica_nodes': [...]
        }
        """
        placements: List[Dict[str, Any]] = []

        online_nodes = self._online_nodes(nodos_registrados)
        if not online_nodes:
            return False, [], 'No hay nodos ONLINE para almacenar bloques.'

        free_by_node = self._free_blocks_by_node(blocks_raw)

        # Filtrar nodes que realmente tengan bloques libres
        candidate_nodes = [n for n in online_nodes if free_by_node.get(n)]
        if not candidate_nodes:
            return False, [], 'No hay bloques libres disponibles en nodos ONLINE.'

        # Round-robin index over candidate_nodes
        node_count = len(candidate_nodes)
        rr_index = 0

        # Ajustar factor de réplica en función de nodos disponibles
        replication_effective = min(self.replication, max(1, node_count))

        # Copia local de listas para consumir sin modificar original
        free_local = {n: list(v) for n, v in free_by_node.items()}

        for i in range(num_blocks):
            # seleccionar primary node por round-robin saltando nodos sin bloques
            tries = 0
            primary_node = None
            while tries < node_count:
                candidate = candidate_nodes[rr_index % node_count]
                rr_index += 1
                tries += 1
                if free_local.get(candidate):
                    primary_node = candidate
                    break

            if not primary_node:
                return False, placements, f'No se pudo asignar primary para el bloque {i+1} (no hay bloques libres).'

            primary_block_id = free_local[primary_node].pop(0)

            # Elegir réplicas en nodos distintos
            replica_block_ids = []
            replica_nodes = []

            if replication_effective > 1:
                # recorrer nodes en orden circular empezando por siguiente al primary
                j = 0
                needed = replication_effective - 1
                # construir lista de nodos candidatos excluyendo primary
                other_nodes = [n for n in candidate_nodes if n != primary_node]
                on_count = len(other_nodes)
                k = 0
                while needed > 0 and on_count > 0:
                    node_pick = other_nodes[k % on_count]
                    k += 1
                    if free_local.get(node_pick):
                        replica_block_ids.append(free_local[node_pick].pop(0))
                        replica_nodes.append(node_pick)
                        needed -= 1
                    else:
                        # si no tiene bloques libres, skip
                        pass

                if needed > 0:
                    # Si no hay suficientes nodos distintos con bloques libres, intentamos
                    # completar réplicas en nodos ya usados (cae en el mismo nodo),
                    # para sistemas de un solo nodo esto evita error.
                    # Recorremos candidate_nodes buscando bloques adicionales aunque sean del primary.
                    for extra_node in candidate_nodes:
                        if needed <= 0:
                            break
                        if extra_node == primary_node:
                            # intentar obtener más bloques del primary si tiene
                            if free_local.get(extra_node):
                                replica_block_ids.append(free_local[extra_node].pop(0))
                                replica_nodes.append(extra_node)
                                needed -= 1
                        else:
                            if free_local.get(extra_node):
                                replica_block_ids.append(free_local[extra_node].pop(0))
                                replica_nodes.append(extra_node)
                                needed -= 1

                if needed > 0:
                    return False, placements, f'No hay suficientes bloques libres para crear {replication_effective} réplicas para el bloque {i+1}.'

            placement = {
                'file_block_index': i + 1,
                'primary_block_id': primary_block_id,
                'primary_node': primary_node,
                'replica_block_ids': replica_block_ids,
                'replica_nodes': replica_nodes
            }
            placements.append(placement)

        return True, placements, 'OK'
