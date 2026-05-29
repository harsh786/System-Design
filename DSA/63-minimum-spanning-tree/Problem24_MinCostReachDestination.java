import java.util.*;
public class Problem24_MinCostReachDestination {
    public int minCost(int n, int[][] edges, int src, int dst) {
        List<int[]>[] adj=new List[n]; for(int i=0;i<n;i++) adj[i]=new ArrayList<>();
        for(int[] e:edges){adj[e[0]].add(new int[]{e[1],e[2]});adj[e[1]].add(new int[]{e[0],e[2]});}
        int[] dist=new int[n]; Arrays.fill(dist,Integer.MAX_VALUE); dist[src]=0;
        PriorityQueue<int[]> pq=new PriorityQueue<>((a,b)->a[1]-b[1]);
        pq.offer(new int[]{src,0});
        while(!pq.isEmpty()){int[] c=pq.poll(); if(c[1]>dist[c[0]]) continue;
            for(int[] ne:adj[c[0]]){int d=c[1]+ne[1]; if(d<dist[ne[0]]){dist[ne[0]]=d;pq.offer(new int[]{ne[0],d});}}}
        return dist[dst]==Integer.MAX_VALUE?-1:dist[dst];
    }
    public static void main(String[] args){
        Problem24_MinCostReachDestination s=new Problem24_MinCostReachDestination();
        System.out.println(s.minCost(5,new int[][]{{0,1,2},{1,2,3},{0,3,6},{3,4,1},{2,4,5}},0,4)); // 7
    }
}
