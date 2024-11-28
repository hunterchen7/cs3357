def parse_input():
    # read the size of the matrix
    n = int(input().strip())
    adjacency_matrix = []
    
    # read the adjacency matrix entries
    for _ in range(n * n):
        value = input().strip()
        if value == 'f':  # representing infinity
            adjacency_matrix.append(float('inf'))
        else:
            adjacency_matrix.append(int(value))
    
    # reshape the adjacency matrix into an nxn grid
    matrix = [adjacency_matrix[i * n:(i + 1) * n] for i in range(n)]
    return n, matrix

def bellman_ford(n, graph, start_node):
    # initialize distances with infinity
    distance = [float('inf')] * n
    distance[start_node] = 0
    
    # relax edges up to (n-1) times
    for _ in range(n - 1):
        for u in range(n):
            for v in range(n):
                if graph[u][v] != float('inf') and distance[u] != float('inf'):
                    distance[v] = min(distance[v], distance[u] + graph[u][v])
    
    # check for negative-weight cycles
    for u in range(n):
        for v in range(n):
            if graph[u][v] != float('inf') and distance[u] != float('inf') and distance[u] + graph[u][v] < distance[v]:
                return [None] * n  # negative cycle detected
    
    # replace float('inf') with none for unreachable nodes
    distance = [None if d == float('inf') else d for d in distance]
    return distance

def main():
    n, graph = parse_input()
    results = []
    
    for node in range(n):
        results.append(bellman_ford(n, graph, node))
    
    for i, distances in enumerate(results):
        print(f"Node {i}: {distances}")

if __name__ == "__main__":
    main()
