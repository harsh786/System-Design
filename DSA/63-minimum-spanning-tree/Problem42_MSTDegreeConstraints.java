import java.util.*;
public class Problem42_MSTDegreeConstraints {
    /* Approximate degree-constrained MST: build MST, check degree constraints */
    public int constrainedMST(int n, int[][] edges, int maxDegree) {
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n],degree=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int cost=0;
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);
            if(u!=v&&degree[e[0]]<maxDegree&&degree[e[1]]<maxDegree){p[u]=v;cost+=e[2];degree[e[0]]++;degree[e[1]]++;}}
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem42_MSTDegreeConstraints s=new Problem42_MSTDegreeConstraints();
        System.out.println(s.constrainedMST(5,new int[][]{{0,1,1},{0,2,2},{0,3,3},{0,4,4},{1,2,5},{2,3,6},{3,4,7}},2));
    }
}
