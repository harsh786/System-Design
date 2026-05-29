import java.util.*;
public class Problem50_MSTLowerBoundTSP {
    /* MST weight is a lower bound for TSP optimal tour */
    public void demonstrate(int[][] dist) {
        int n=dist.length;
        boolean[] vis=new boolean[n]; int[] key=new int[n]; Arrays.fill(key,Integer.MAX_VALUE); key[0]=0;
        int mstCost=0;
        for(int c=0;c<n;c++){int u=-1; for(int i=0;i<n;i++) if(!vis[i]&&(u==-1||key[i]<key[u])) u=i;
            vis[u]=true;mstCost+=key[u];
            for(int v=0;v<n;v++) if(!vis[v]&&dist[u][v]<key[v]) key[v]=dist[u][v];}
        // Nearest neighbor heuristic for TSP upper bound
        Arrays.fill(vis,false); vis[0]=true; int cur=0,tspCost=0;
        for(int c=1;c<n;c++){int best=-1;
            for(int v=0;v<n;v++) if(!vis[v]&&(best==-1||dist[cur][v]<dist[cur][best])) best=v;
            vis[best]=true;tspCost+=dist[cur][best];cur=best;}
        tspCost+=dist[cur][0];
        System.out.println("MST (lower bound): "+mstCost);
        System.out.println("NN TSP (upper bound): "+tspCost);
        System.out.println("Optimal TSP is in ["+mstCost+", "+tspCost+"]");
    }
    public static void main(String[] args){
        Problem50_MSTLowerBoundTSP s=new Problem50_MSTLowerBoundTSP();
        s.demonstrate(new int[][]{{0,10,15,20},{10,0,35,25},{15,35,0,30},{20,25,30,0}});
    }
}
