import java.util.*;
public class Problem29_BucketSortHistogramBins {
    public int[] histogram(double[] data, int numBins, double min, double max) {
        int[] bins=new int[numBins];
        double width=(max-min)/numBins;
        for(double x:data){int idx=(int)((x-min)/width);if(idx>=numBins) idx=numBins-1;if(idx>=0) bins[idx]++;}
        return bins;
    }
    public static void main(String[] args){ Random r=new Random(42); double[] d=new double[1000]; for(int i=0;i<1000;i++) d[i]=r.nextGaussian(); System.out.println(Arrays.toString(new Problem29_BucketSortHistogramBins().histogram(d,10,-3,3))); }
}
