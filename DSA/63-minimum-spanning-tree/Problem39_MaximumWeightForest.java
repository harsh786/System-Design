import java.util.*;
public class Problem39_MaximumWeightForest {
    /* Maximum weight forest: include edges greedily (heaviest first) without creating cycles */
    public int maxForest(int n, int[][] edges) {
        Arrays.sort(edges,(a,b)->b[2]-a[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int weight=0;
        for(int[] e:edges){if(e[2]<=0) break; // only include positive edges
            int u=find(p,e[0]),v=find(p,e[1]);if(u!=v){p[u]=v;weight+=e[2];}}
        return weight;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem39_MaximumWeightForest s=new Problem39_MaximumWeightForest();
        System.out.println(s.maxForest(4,new int[][]{{0,1,5},{1,2,-3},{2,3,4},{0,3,2}})); // 11
    }
}
