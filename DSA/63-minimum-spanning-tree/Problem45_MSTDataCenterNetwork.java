import java.util.*;
public class Problem45_MSTDataCenterNetwork {
    public int minCostNetwork(int numDCs, int[][] links) {
        Arrays.sort(links,(a,b)->a[2]-b[2]);
        int[] p=new int[numDCs]; for(int i=0;i<numDCs;i++) p[i]=i;
        int cost=0,edges=0;
        for(int[] l:links){int u=find(p,l[0]),v=find(p,l[1]);if(u!=v){p[u]=v;cost+=l[2];edges++;}}
        return edges==numDCs-1?cost:-1;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem45_MSTDataCenterNetwork s=new Problem45_MSTDataCenterNetwork();
        System.out.println(s.minCostNetwork(5,new int[][]{{0,1,10},{0,2,20},{1,2,5},{1,3,15},{2,3,8},{3,4,12},{2,4,18}}));
    }
}
