import java.util.*;
public class Problem48_MSTEdgeSensitivity {
    /* How much can each MST edge weight increase before MST changes? */
    public int[] sensitivity(int n, int[][] edges) {
        Arrays.sort(edges,(a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        List<int[]> mstEdges=new ArrayList<>(); List<int[]> nonMstEdges=new ArrayList<>();
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);if(u!=v){p[u]=v;mstEdges.add(e);} else nonMstEdges.add(e);}
        int[] sens=new int[mstEdges.size()];
        Arrays.fill(sens,Integer.MAX_VALUE);
        // For each non-MST edge, find which MST edges it could replace
        for(int[] ne:nonMstEdges){
            // The sensitivity of MST edge on path(u,v) is min(ne.weight - mstEdge.weight)
            // Simplified: for each MST edge, min non-tree edge crossing that cut minus edge weight
            for(int i=0;i<mstEdges.size();i++){
                // Check if removing mstEdges[i] disconnects ne[0] from ne[1]
                for(int j=0;j<n;j++) p[j]=j;
                for(int j=0;j<mstEdges.size();j++){if(j==i) continue; int u=find(p,mstEdges.get(j)[0]),v=find(p,mstEdges.get(j)[1]);if(u!=v) p[u]=v;}
                if(find(p,ne[0])!=find(p,ne[1])) sens[i]=Math.min(sens[i],ne[2]-mstEdges.get(i)[2]);
            }
        }
        return sens;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem48_MSTEdgeSensitivity s=new Problem48_MSTEdgeSensitivity();
        System.out.println(Arrays.toString(s.sensitivity(4,new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})));
    }
}
