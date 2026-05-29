import java.util.*;

public class Problem48_PowerOfRandomPivots {
    // Compare fixed vs random pivot quicksort on sorted input
    static int comparisons;

    static void qsortFixed(int[] a, int lo, int hi) {
        if(lo>=hi)return; int p=a[hi],i=lo;
        for(int j=lo;j<hi;j++){comparisons++;if(a[j]<=p){int t=a[i];a[i]=a[j];a[j]=t;i++;}}
        int t=a[i];a[i]=a[hi];a[hi]=t; qsortFixed(a,lo,i-1);qsortFixed(a,i+1,hi);
    }

    static Random rand=new Random();
    static void qsortRandom(int[] a, int lo, int hi) {
        if(lo>=hi)return; int pi=lo+rand.nextInt(hi-lo+1);int t=a[pi];a[pi]=a[hi];a[hi]=t;
        int p=a[hi],i=lo;
        for(int j=lo;j<hi;j++){comparisons++;if(a[j]<=p){t=a[i];a[i]=a[j];a[j]=t;i++;}}
        t=a[i];a[i]=a[hi];a[hi]=t; qsortRandom(a,lo,i-1);qsortRandom(a,i+1,hi);
    }

    public static void main(String[] args) {
        int n=1000; int[] sorted=new int[n]; for(int i=0;i<n;i++)sorted[i]=i;
        comparisons=0; qsortFixed(sorted.clone(),0,n-1);
        System.out.println("Fixed pivot on sorted: "+comparisons+" comparisons");
        comparisons=0; qsortRandom(sorted.clone(),0,n-1);
        System.out.println("Random pivot on sorted: "+comparisons+" comparisons");
    }
}
