import java.util.*;
public class Problem33_ManhattanMST {
    public long manhattanMST(int[][] points) {
        int n=points.length;
        List<long[]> edges=new ArrayList<>();
        for(int i=0;i<n;i++) for(int j=i+1;j<n;j++)
            edges.add(new long[]{Math.abs((long)points[i][0]-points[j][0])+Math.abs((long)points[i][1]-points[j][1]),i,j});
        edges.sort((a,b)->Long.compare(a[0],b[0]));
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        long cost=0;
        for(long[] e:edges){int u=find(p,(int)e[1]),v=find(p,(int)e[2]);if(u!=v){p[u]=v;cost+=e[0];}}
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem33_ManhattanMST s=new Problem33_ManhattanMST();
        System.out.println(s.manhattanMST(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}})); // 20
    }
}
