import java.util.*;
public class Problem31_DistributedMST {
    /* Concept: GHS algorithm simulation - each node finds minimum outgoing edge */
    public int simulateDistributedMST(int n, int[][] edges) {
        // Simulates Boruvka's (basis of GHS)
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int cost=0,components=n;
        while(components>1){
            int[] cheap=new int[n]; Arrays.fill(cheap,-1);
            for(int i=0;i<edges.length;i++){int u=find(p,edges[i][0]),v=find(p,edges[i][1]);
                if(u==v) continue;
                if(cheap[u]==-1||edges[i][2]<edges[cheap[u]][2]) cheap[u]=i;
                if(cheap[v]==-1||edges[i][2]<edges[cheap[v]][2]) cheap[v]=i;}
            for(int i=0;i<n;i++){if(cheap[i]!=-1){int u=find(p,edges[cheap[i]][0]),v=find(p,edges[cheap[i]][1]);
                if(u!=v){p[u]=v;cost+=edges[cheap[i]][2];components--;}}}
        }
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem31_DistributedMST s=new Problem31_DistributedMST();
        System.out.println(s.simulateDistributedMST(4,new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}}));
    }
}
