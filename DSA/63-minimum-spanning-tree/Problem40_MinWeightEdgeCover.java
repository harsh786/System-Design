import java.util.*;
public class Problem40_MinWeightEdgeCover {
    /* Min weight edge cover: MST + minimum weight edges for isolated vertices */
    public int minEdgeCover(int n, int[][] edges) {
        // For connected graph: minimum edge cover = n - max matching
        // Greedy approximation: pick cheapest edge for each uncovered vertex
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        boolean[] covered=new boolean[n];
        int cost=0;
        for(int[] e:edges){if(!covered[e[0]]||!covered[e[1]]){cost+=e[2];covered[e[0]]=true;covered[e[1]]=true;}}
        return cost;
    }
    public static void main(String[] args){
        Problem40_MinWeightEdgeCover s=new Problem40_MinWeightEdgeCover();
        System.out.println(s.minEdgeCover(4,new int[][]{{0,1,1},{1,2,2},{2,3,3},{0,3,4}})); // 4
    }
}
