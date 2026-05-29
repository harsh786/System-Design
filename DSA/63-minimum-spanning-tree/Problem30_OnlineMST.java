import java.util.*;
public class Problem30_OnlineMST {
    /* Online MST: maintain MST as edges arrive one by one */
    private int n; private List<int[]> mstEdges=new ArrayList<>();
    public Problem30_OnlineMST(int n){this.n=n;}
    public int addEdge(int u,int v,int w){
        mstEdges.add(new int[]{u,v,w});
        // If cycle formed, remove heaviest edge
        mstEdges.sort((a,b)->a[2]-b[2]);
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        List<int[]> newMST=new ArrayList<>();
        for(int[] e:mstEdges){int pu=find(p,e[0]),pv=find(p,e[1]);if(pu!=pv){p[pu]=pv;newMST.add(e);}}
        mstEdges=newMST;
        int cost=0; for(int[] e:mstEdges) cost+=e[2];
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem30_OnlineMST s=new Problem30_OnlineMST(4);
        System.out.println(s.addEdge(0,1,5));
        System.out.println(s.addEdge(1,2,3));
        System.out.println(s.addEdge(0,2,1));
        System.out.println(s.addEdge(2,3,4));
    }
}
