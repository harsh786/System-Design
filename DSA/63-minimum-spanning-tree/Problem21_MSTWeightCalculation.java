import java.util.*;
public class Problem21_MSTWeightCalculation {
    public long mstWeight(int n, int[][] edges) {
        Arrays.sort(edges, (a,b)->a[2]-b[2]);
        int[] p = new int[n]; for(int i=0;i<n;i++) p[i]=i;
        long w=0;
        for(int[] e:edges){int u=find(p,e[0]),v=find(p,e[1]);if(u!=v){p[u]=v;w+=e[2];}}
        return w;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem21_MSTWeightCalculation s=new Problem21_MSTWeightCalculation();
        System.out.println(s.mstWeight(4,new int[][]{{0,1,10},{0,2,6},{0,3,5},{1,3,15},{2,3,4}})); // 19
    }
}
