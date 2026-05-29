import java.util.*;
public class Problem47_MSTCommunicationNetwork {
    /* Build minimum cost communication network with redundancy (MST + cheapest extra edge) */
    public int[] mstPlusRedundancy(int n, int[][] edges) {
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int mstCost=0; int extraEdge=Integer.MAX_VALUE;
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);
            if(u!=v){p[u]=v;mstCost+=e[2];} else extraEdge=Math.min(extraEdge,e[2]);}
        return new int[]{mstCost, mstCost+(extraEdge==Integer.MAX_VALUE?0:extraEdge)};
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem47_MSTCommunicationNetwork s=new Problem47_MSTCommunicationNetwork();
        System.out.println(Arrays.toString(s.mstPlusRedundancy(4,new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})));
    }
}
