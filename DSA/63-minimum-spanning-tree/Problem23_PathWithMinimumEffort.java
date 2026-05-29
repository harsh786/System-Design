import java.util.*;
public class Problem23_PathWithMinimumEffort {
    public int minimumEffortPath(int[][] heights) {
        int m=heights.length,n=heights[0].length;
        int[][] dist=new int[m][n]; for(int[] r:dist) Arrays.fill(r,Integer.MAX_VALUE);
        dist[0][0]=0;
        PriorityQueue<int[]> pq=new PriorityQueue<>((a,b)->a[2]-b[2]);
        pq.offer(new int[]{0,0,0});
        int[][] dirs={{0,1},{0,-1},{1,0},{-1,0}};
        while(!pq.isEmpty()){
            int[] c=pq.poll();
            if(c[0]==m-1&&c[1]==n-1) return c[2];
            if(c[2]>dist[c[0]][c[1]]) continue;
            for(int[] d:dirs){int nr=c[0]+d[0],nc=c[1]+d[1];
                if(nr>=0&&nr<m&&nc>=0&&nc<n){int eff=Math.max(c[2],Math.abs(heights[nr][nc]-heights[c[0]][c[1]]));
                if(eff<dist[nr][nc]){dist[nr][nc]=eff;pq.offer(new int[]{nr,nc,eff});}}}
        }
        return dist[m-1][n-1];
    }
    public static void main(String[] args){
        Problem23_PathWithMinimumEffort s=new Problem23_PathWithMinimumEffort();
        System.out.println(s.minimumEffortPath(new int[][]{{1,2,2},{3,8,2},{5,3,5}})); // 2
    }
}
