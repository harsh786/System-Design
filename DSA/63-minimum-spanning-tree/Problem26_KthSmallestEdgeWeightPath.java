import java.util.*;
public class Problem26_KthSmallestEdgeWeightPath {
    /* Find path where k-th largest edge weight is minimized - use MST property */
    public int kthSmallestMaxEdge(int n, int[][] edges, int src, int dst) {
        // In MST, path between any two nodes minimizes the maximum edge (bottleneck)
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        for(int[] e:edges){p[find(p,e[0])]=find(p,e[1]); if(find(p,src)==find(p,dst)) return e[2];}
        return -1;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem26_KthSmallestEdgeWeightPath s=new Problem26_KthSmallestEdgeWeightPath();
        System.out.println(s.kthSmallestMaxEdge(4,new int[][]{{0,1,1},{1,2,2},{2,3,3},{0,3,10}},0,3)); // 3
    }
}
