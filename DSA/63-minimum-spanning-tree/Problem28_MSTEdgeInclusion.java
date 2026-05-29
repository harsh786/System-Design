import java.util.*;
public class Problem28_MSTEdgeInclusion {
    public int mstWith(int n, int[][] edges, int includeIdx) {
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        p[find(p,edges[includeIdx][0])]=find(p,edges[includeIdx][1]);
        int cost=edges[includeIdx][2];
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        for(int i=0;i<edges.length;i++){if(i==includeIdx) continue;
            int u=find(p,edges[i][0]),v=find(p,edges[i][1]);if(u!=v){p[u]=v;cost+=edges[i][2];}}
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem28_MSTEdgeInclusion s=new Problem28_MSTEdgeInclusion();
        System.out.println(s.mstWith(4,new int[][]{{0,1,1},{1,2,2},{0,2,3},{2,3,4}},2)); // 8
    }
}
