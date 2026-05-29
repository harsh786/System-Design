import java.util.*;

public class Problem33_FindTwoMissingNumbers {
    // Array 1..n with 2 missing, can query sum and sum of squares
    static int[] present = {1,2,4,5,7}; // missing 3,6 from 1..7
    
    static long querySum() { long s=0; for(int x:present) s+=x; return s; }
    static long querySumSq() { long s=0; for(int x:present) s+=(long)x*x; return s; }
    
    static int[] findMissing(int n) {
        long expectedSum = (long)n*(n+1)/2;
        long expectedSumSq = (long)n*(n+1)*(2*n+1)/6;
        long a_plus_b = expectedSum - querySum();
        long a2_plus_b2 = expectedSumSq - querySumSq();
        // a+b=s, a^2+b^2=q => (a-b)^2 = 2q - s^2
        long diff = (long)Math.sqrt(2*a2_plus_b2 - a_plus_b*a_plus_b);
        int a = (int)(a_plus_b + diff) / 2;
        int b = (int)(a_plus_b - diff) / 2;
        return new int[]{a, b};
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(findMissing(7))); // [6,3]
    }
}
