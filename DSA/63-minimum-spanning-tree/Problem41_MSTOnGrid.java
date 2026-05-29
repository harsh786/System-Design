import java.util.*;
public class Problem41_MSTOnGrid {
    public int mstGrid(int[][] grid) {
        int m=grid.length,n=grid[0].length;
        List<int[]> edges=new ArrayList<>();
        for(int i=0;i<m;i++) for(int j=0;j<n;j++){
            if(j+1<n) edges.add(new int[]{i*n+j,i*n+j+1,Math.abs(grid[i][j]-grid[i][j+1])});
            if(i+1<m) edges.add(new int[]{i*n+j,(i+1)*n+j,Math.abs(grid[i][j]-grid[i+1][j])});}
        edges.sort((a,b)->a[2]-b[2]);
        int[] p=new int[m*n]; for(int i=0;i<m*n;i++) p[i]=i;
        int cost=0;
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);if(u!=v){p[u]=v;cost+=e[2];}}
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem41_MSTOnGrid s=new Problem41_MSTOnGrid();
        System.out.println(s.mstGrid(new int[][]{{1,3,5},{2,4,6},{7,8,9}}));
    }
}
