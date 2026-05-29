import java.util.*;
public class Problem29_DynamicMST {
    /* Concept: recompute MST when edges are added/removed */
    private int n; private List<int[]> edges=new ArrayList<>();
    public Problem29_DynamicMST(int n){this.n=n;}
    public void addEdge(int u,int v,int w){edges.add(new int[]{u,v,w});}
    public int getMSTWeight(){
        edges.sort((a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        int cost=0;
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);if(u!=v){p[u]=v;cost+=e[2];}}
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem29_DynamicMST s=new Problem29_DynamicMST(4);
        s.addEdge(0,1,1);s.addEdge(1,2,2);s.addEdge(2,3,3);
        System.out.println("MST: "+s.getMSTWeight());
        s.addEdge(0,3,2);
        System.out.println("MST after adding 0-3: "+s.getMSTWeight());
    }
}
