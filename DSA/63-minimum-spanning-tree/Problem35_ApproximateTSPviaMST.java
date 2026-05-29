import java.util.*;
public class Problem35_ApproximateTSPviaMST {
    /* 2-approximation: build MST, DFS preorder gives tour <= 2*OPT */
    public List<Integer> approxTSP(int n, int[][] dist) {
        // Prim's MST
        boolean[] vis=new boolean[n]; int[] parent=new int[n]; int[] key=new int[n];
        Arrays.fill(key,Integer.MAX_VALUE); key[0]=0; parent[0]=-1;
        for(int c=0;c<n;c++){int u=-1;
            for(int i=0;i<n;i++) if(!vis[i]&&(u==-1||key[i]<key[u])) u=i;
            vis[u]=true;
            for(int v=0;v<n;v++) if(!vis[v]&&dist[u][v]<key[v]){key[v]=dist[u][v];parent[v]=u;}}
        List<Integer>[] adj=new List[n]; for(int i=0;i<n;i++) adj[i]=new ArrayList<>();
        for(int i=1;i<n;i++){adj[parent[i]].add(i);adj[i].add(parent[i]);}
        List<Integer> tour=new ArrayList<>();
        boolean[] visited=new boolean[n];
        dfs(0,adj,visited,tour);
        tour.add(0);
        return tour;
    }
    private void dfs(int u,List<Integer>[] adj,boolean[] vis,List<Integer> tour){vis[u]=true;tour.add(u);for(int v:adj[u]) if(!vis[v]) dfs(v,adj,vis,tour);}
    public static void main(String[] args){
        Problem35_ApproximateTSPviaMST s=new Problem35_ApproximateTSPviaMST();
        int[][] dist={{0,10,15,20},{10,0,35,25},{15,35,0,30},{20,25,30,0}};
        System.out.println(s.approxTSP(4,dist));
    }
}
