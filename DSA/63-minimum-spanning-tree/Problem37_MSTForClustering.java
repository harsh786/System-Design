import java.util.*;
public class Problem37_MSTForClustering {
    /* K-clustering: build MST, remove k-1 heaviest edges to get k clusters */
    public List<List<Integer>> cluster(int n, int[][] edges, int k) {
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int edgesAdded=0;
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);
            if(u!=v){p[u]=v;edgesAdded++;if(edgesAdded==n-k) break;}} // stop k-1 edges early
        Map<Integer,List<Integer>> clusters=new HashMap<>();
        for(int i=0;i<n;i++) clusters.computeIfAbsent(find(p,i),x->new ArrayList<>()).add(i);
        return new ArrayList<>(clusters.values());
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem37_MSTForClustering s=new Problem37_MSTForClustering();
        System.out.println(s.cluster(6,new int[][]{{0,1,1},{1,2,2},{2,3,10},{3,4,1},{4,5,2},{0,5,15}},2));
    }
}
