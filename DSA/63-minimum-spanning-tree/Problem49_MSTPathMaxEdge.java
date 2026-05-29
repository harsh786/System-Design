import java.util.*;
public class Problem49_MSTPathMaxEdge {
    /* In MST, path between u and v has minimum possible maximum edge (minimax path) */
    public int minimaxPath(int n, int[][] edges, int src, int dst) {
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        for(int[] e:edges){p[find(p,e[0])]=find(p,e[1]);if(find(p,src)==find(p,dst)) return e[2];}
        return -1;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem49_MSTPathMaxEdge s=new Problem49_MSTPathMaxEdge();
        System.out.println(s.minimaxPath(4,new int[][]{{0,1,1},{1,2,2},{2,3,3},{0,3,10}},0,3)); // 3
    }
}
