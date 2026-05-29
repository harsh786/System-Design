import java.util.*;
public class Problem46_MSTRoadNetworkPlanning {
    public int minRoadCost(int[][] cities) {
        int n=cities.length;
        boolean[] vis=new boolean[n]; int[] key=new int[n]; Arrays.fill(key,Integer.MAX_VALUE); key[0]=0;
        int cost=0;
        for(int c=0;c<n;c++){int u=-1; for(int i=0;i<n;i++) if(!vis[i]&&(u==-1||key[i]<key[u])) u=i;
            vis[u]=true;cost+=key[u];
            for(int v=0;v<n;v++) if(!vis[v]){int d=Math.abs(cities[u][0]-cities[v][0])+Math.abs(cities[u][1]-cities[v][1]);if(d<key[v]) key[v]=d;}}
        return cost;
    }
    public static void main(String[] args){
        Problem46_MSTRoadNetworkPlanning s=new Problem46_MSTRoadNetworkPlanning();
        System.out.println(s.minRoadCost(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}})); // 20
    }
}
