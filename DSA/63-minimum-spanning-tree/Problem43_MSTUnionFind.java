import java.util.*;
public class Problem43_MSTUnionFind {
    private int[] parent,rank;
    public Problem43_MSTUnionFind(int n){parent=new int[n];rank=new int[n];for(int i=0;i<n;i++) parent[i]=i;}
    public int find(int x){return parent[x]==x?x:(parent[x]=find(parent[x]));}
    public boolean union(int a,int b){int pa=find(a),pb=find(b);if(pa==pb) return false;
        if(rank[pa]<rank[pb]) parent[pa]=pb; else if(rank[pa]>rank[pb]) parent[pb]=pa; else{parent[pb]=pa;rank[pa]++;}return true;}

    public static int kruskal(int n, int[][] edges){
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        Problem43_MSTUnionFind uf=new Problem43_MSTUnionFind(n);
        int cost=0;
        for(int[] e:edges) if(uf.union(e[0],e[1])) cost+=e[2];
        return cost;
    }
    public static void main(String[] args){
        System.out.println(kruskal(4,new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}}));
    }
}
