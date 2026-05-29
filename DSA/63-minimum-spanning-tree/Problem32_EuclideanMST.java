import java.util.*;
public class Problem32_EuclideanMST {
    public double euclideanMST(double[][] points) {
        int n=points.length;
        List<double[]> edges=new ArrayList<>();
        for(int i=0;i<n;i++) for(int j=i+1;j<n;j++)
            edges.add(new double[]{Math.hypot(points[i][0]-points[j][0],points[i][1]-points[j][1]),i,j});
        edges.sort((a,b)->Double.compare(a[0],b[0]));
        int[] p=new int[n]; for(int i=0;i<n;i++) p[i]=i;
        double cost=0;
        for(double[] e:edges){int u=find(p,(int)e[1]),v=find(p,(int)e[2]);if(u!=v){p[u]=v;cost+=e[0];}}
        return cost;
    }
    private int find(int[] p,int x){return p[x]==x?x:(p[x]=find(p,p[x]));}
    public static void main(String[] args){
        Problem32_EuclideanMST s=new Problem32_EuclideanMST();
        System.out.printf("%.4f%n",s.euclideanMST(new double[][]{{0,0},{1,1},{2,0},{1,-1}}));
    }
}
