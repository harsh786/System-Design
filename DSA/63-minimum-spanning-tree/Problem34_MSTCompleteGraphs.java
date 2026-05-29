import java.util.*;
public class Problem34_MSTCompleteGraphs {
    /* For complete graph with n vertices, MST has n-1 edges. Prim's is O(n^2) which is optimal. */
    public int mstComplete(int[][] dist) {
        int n=dist.length; boolean[] vis=new boolean[n]; int[] key=new int[n];
        Arrays.fill(key,Integer.MAX_VALUE); key[0]=0;
        int cost=0;
        for(int c=0;c<n;c++){int u=-1;
            for(int i=0;i<n;i++) if(!vis[i]&&(u==-1||key[i]<key[u])) u=i;
            vis[u]=true; cost+=key[u];
            for(int v=0;v<n;v++) if(!vis[v]&&dist[u][v]<key[v]) key[v]=dist[u][v];}
        return cost;
    }
    public static void main(String[] args){
        Problem34_MSTCompleteGraphs s=new Problem34_MSTCompleteGraphs();
        int[][] dist={{0,2,3,1},{2,0,4,2},{3,4,0,5},{1,2,5,0}};
        System.out.println(s.mstComplete(dist)); // 5
    }
}
