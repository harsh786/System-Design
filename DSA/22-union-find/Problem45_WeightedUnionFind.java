import java.util.*;

/**
 * Problem 45: Weighted Union-Find
 * 
 * Union-Find where each edge has a weight representing the ratio/distance
 * between a node and its parent. Used in problems like Evaluate Division.
 * 
 * Key operations:
 * - find(x): returns root, updates weight[x] to be distance from x to root
 * - union(x, y, w): merge components knowing x/y = w (or dist(x,y) = w)
 * - query(x, y): return x/y if in same component
 * 
 * Time: O(α(n)) per operation with path compression, Space: O(n)
 * 
 * Production Analogy: Currency exchange, unit conversion, or relative distance
 * tracking between nodes in a distributed system.
 */
public class Problem45_WeightedUnionFind {
    
    int[] parent, rank;
    double[] weight; // weight[i] = value of i / value of parent[i]
    
    public Problem45_WeightedUnionFind(int n) {
        parent = new int[n]; rank = new int[n]; weight = new double[n];
        for (int i = 0; i < n; i++) { parent[i] = i; weight[i] = 1.0; }
    }
    
    public int find(int x) {
        if (parent[x] != x) {
            int root = find(parent[x]);
            weight[x] *= weight[parent[x]]; // x/root = (x/parent) * (parent/root)
            parent[x] = root;
        }
        return parent[x];
    }
    
    // x / y = w
    public void union(int x, int y, double w) {
        int px = find(x), py = find(y);
        if (px == py) return;
        // weight[x] = x/px, weight[y] = y/py
        // x/y = w => px/py = w * weight[y] / weight[x]
        if (rank[px] < rank[py]) {
            parent[px] = py;
            weight[px] = w * weight[y] / weight[x];
        } else if (rank[px] > rank[py]) {
            parent[py] = px;
            weight[py] = weight[x] / (w * weight[y]);
        } else {
            parent[py] = px;
            weight[py] = weight[x] / (w * weight[y]);
            rank[px]++;
        }
    }
    
    // Returns x / y, or -1 if not connected
    public double query(int x, int y) {
        if (find(x) != find(y)) return -1.0;
        return weight[x] / weight[y]; // (x/root) / (y/root) = x/y
    }
    
    public static void main(String[] args) {
        Problem45_WeightedUnionFind uf = new Problem45_WeightedUnionFind(4);
        // a=0, b=1, c=2, d=3
        uf.union(0, 1, 2.0); // a/b = 2
        uf.union(1, 2, 3.0); // b/c = 3
        
        System.out.println(uf.query(0, 2)); // a/c = 6.0
        System.out.println(uf.query(2, 0)); // c/a = 0.166...
        System.out.println(uf.query(0, 3)); // -1.0 (not connected)
        
        uf.union(2, 3, 0.5); // c/d = 0.5
        System.out.println(uf.query(0, 3)); // a/d = 3.0
    }
}
