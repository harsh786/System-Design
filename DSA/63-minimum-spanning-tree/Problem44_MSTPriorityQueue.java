import java.util.*;
public class Problem44_MSTPriorityQueue {
    public int primPQ(int n, List<int[]>[] adj) {
        boolean[] vis=new boolean[n];
        PriorityQueue<int[]> pq=new PriorityQueue<>((a,b)->a[1]-b[1]);
        pq.offer(new int[]{0,0}); int cost=0,count=0;
        while(count<n){int[] c=pq.poll();if(vis[c[0]]) continue;vis[c[0]]=true;cost+=c[1];count++;
            for(int[] ne:adj[c[0]]) if(!vis[ne[0]]) pq.offer(new int[]{ne[0],ne[1]});}
        return cost;
    }
    public static void main(String[] args){
        int n=4; List<int[]>[] adj=new List[n]; for(int i=0;i<n;i++) adj[i]=new ArrayList<>();
        int[][] edges={{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}};
        for(int[] e:edges){adj[e[0]].add(new int[]{e[1],e[2]});adj[e[1]].add(new int[]{e[0],e[2]});}
        Problem44_MSTPriorityQueue s=new Problem44_MSTPriorityQueue();
        System.out.println(s.primPQ(n,adj)); // 6
    }
}
