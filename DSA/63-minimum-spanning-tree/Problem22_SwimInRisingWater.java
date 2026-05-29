import java.util.*;
public class Problem22_SwimInRisingWater {
    public int swimInWater(int[][] grid) {
        int n=grid.length;
        PriorityQueue<int[]> pq=new PriorityQueue<>((a,b)->a[2]-b[2]);
        pq.offer(new int[]{0,0,grid[0][0]});
        boolean[][] vis=new boolean[n][n]; vis[0][0]=true;
        int[][] dirs={{0,1},{0,-1},{1,0},{-1,0}};
        while(!pq.isEmpty()){
            int[] c=pq.poll();
            if(c[0]==n-1&&c[1]==n-1) return c[2];
            for(int[] d:dirs){int nr=c[0]+d[0],nc=c[1]+d[1];
                if(nr>=0&&nr<n&&nc>=0&&nc<n&&!vis[nr][nc]){vis[nr][nc]=true;pq.offer(new int[]{nr,nc,Math.max(c[2],grid[nr][nc])});}}
        }
        return -1;
    }
    public static void main(String[] args){
        Problem22_SwimInRisingWater s=new Problem22_SwimInRisingWater();
        System.out.println(s.swimInWater(new int[][]{{0,2},{1,3}})); // 3
    }
}
