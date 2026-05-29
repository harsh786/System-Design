import java.util.*;
public class Problem27_MSTEdgeExclusion {
    public int mstWithout(int n, int[][] edges, int excludeIdx) {
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int cost=0,count=0;
        for(int i=0;i<edges.length;i++){if(i==excludeIdx) continue;
            int u=find(p,edges[i][0]),v=find(p,edges[i][1]);if(u!=v){p[u]=v;cost+=edges[i][2];count++;}}
        return count==n-1?cost:-1;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem27_MSTEdgeExclusion s=new Problem27_MSTEdgeExclusion();
        int[][] edges={{0,1,1},{1,2,2},{0,2,3},{2,3,4}};
        System.out.println(s.mstWithout(4,edges,0)); // 9
    }
}
