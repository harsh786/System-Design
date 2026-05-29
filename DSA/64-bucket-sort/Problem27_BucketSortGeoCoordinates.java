import java.util.*;
public class Problem27_BucketSortGeoCoordinates {
    public double[][] sortByLatitude(double[][] coords) {
        int n=coords.length; List<double[]>[] buckets=new List[180];
        for(int i=0;i<180;i++) buckets[i]=new ArrayList<>();
        for(double[] c:coords) buckets[(int)(c[0]+90)].add(c);
        int idx=0; for(List<double[]> b:buckets){b.sort((a,b2)->Double.compare(a[0],b2[0]));for(double[] c:b) coords[idx++]=c;}
        return coords;
    }
    public static void main(String[] args){ double[][] c={{40.7,-74.0},{34.0,-118.2},{51.5,-0.1},{-33.8,151.2}}; new Problem27_BucketSortGeoCoordinates().sortByLatitude(c); for(double[] p:c) System.out.println(Arrays.toString(p)); }
}
