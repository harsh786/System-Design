import java.util.*;
public class Problem38_SingleLinkageClustering {
    /* Single-linkage = MST-based hierarchical clustering */
    public int[][] dendrogram(int n, int[][] edges) {
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n],size=new int[n]; for(int i=0;i<n;i++){p[i]=i;size[i]=1;}
        int[][] merges=new int[n-1][3]; int idx=0;
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);
            if(u!=v){merges[idx++]=new int[]{u,v,e[2]};p[u]=v;size[v]+=size[u];if(idx==n-1) break;}}
        return merges;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem38_SingleLinkageClustering s=new Problem38_SingleLinkageClustering();
        int[][] d=s.dendrogram(4,new int[][]{{0,1,1},{1,2,3},{2,3,2},{0,3,5}});
        for(int[] m:d) System.out.println(Arrays.toString(m));
    }
}
