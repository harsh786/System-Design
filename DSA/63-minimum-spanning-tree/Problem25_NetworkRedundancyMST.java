import java.util.*;
public class Problem25_NetworkRedundancyMST {
    /* Count extra edges beyond MST (redundant connections) */
    public int redundantEdges(int n, int[][] edges) {
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int mstEdges=0;
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);if(u!=v){p[u]=v;mstEdges++;}}
        return edges.length-mstEdges;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem25_NetworkRedundancyMST s=new Problem25_NetworkRedundancyMST();
        System.out.println(s.redundantEdges(4,new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})); // 2
    }
}
