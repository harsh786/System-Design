import java.util.*;
public class Problem36_ChristofidesAlgorithm {
    /* Christofides concept: MST + min weight perfect matching on odd-degree vertices + Eulerian circuit */
    public int christofidesApprox(int n, int[][] dist) {
        // Simplified: just return MST weight * 1.5 as upper bound concept
        boolean[] vis=new boolean[n]; int[] key=new int[n];
        Arrays.fill(key,Integer.MAX_VALUE); key[0]=0;
        int mstCost=0;
        for(int c=0;c<n;c++){int u=-1;
            for(int i=0;i<n;i++) if(!vis[i]&&(u==-1||key[i]<key[u])) u=i;
            vis[u]=true; mstCost+=key[u];
            for(int v=0;v<n;v++) if(!vis[v]&&dist[u][v]<key[v]) key[v]=dist[u][v];}
        System.out.println("MST cost: "+mstCost);
        System.out.println("Christofides guarantees tour <= 1.5 * MST = "+(int)(1.5*mstCost));
        return (int)(1.5*mstCost);
    }
    public static void main(String[] args){
        Problem36_ChristofidesAlgorithm s=new Problem36_ChristofidesAlgorithm();
        int[][] dist={{0,10,15,20},{10,0,35,25},{15,35,0,30},{20,25,30,0}};
        s.christofidesApprox(4,dist);
    }
}
