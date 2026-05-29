import java.util.*;
public class Problem46_BucketSortLatencyPercentiles {
    /* Sort latencies and compute percentiles using bucket sort */
    public double[] percentiles(int[] latencies, double[] pcts) {
        int max=0; for(int l:latencies) max=Math.max(max,l);
        int[] count=new int[max+1]; for(int l:latencies) count[l]++;
        // prefix sum
        for(int i=1;i<=max;i++) count[i]+=count[i-1];
        double[] result=new double[pcts.length];
        for(int i=0;i<pcts.length;i++){
            int target=(int)Math.ceil(pcts[i]/100.0*latencies.length);
            for(int j=0;j<=max;j++){if(count[j]>=target){result[i]=j;break;}}
        }
        return result;
    }
    public static void main(String[] args){ Random r=new Random(42); int[] lat=new int[10000]; for(int i=0;i<10000;i++) lat[i]=r.nextInt(1000); double[] p=new Problem46_BucketSortLatencyPercentiles().percentiles(lat,new double[]{50,90,95,99}); System.out.println("P50="+p[0]+" P90="+p[1]+" P95="+p[2]+" P99="+p[3]); }
}
