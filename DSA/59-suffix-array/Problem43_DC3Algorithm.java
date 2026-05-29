import java.util.*;

public class Problem43_DC3Algorithm {
    // DC3/Skew algorithm concept: linear time SA construction
    // Split indices into mod-0, mod-1, mod-2 groups
    // Recursively sort mod-1 and mod-2 suffixes, then merge with mod-0

    // Simplified demo using naive sort
    public static int[] buildSA(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++) sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    public static void main(String[] args) {
        String s = "yabbadabbado";
        int[] sa = buildSA(s);
        System.out.println("DC3 concept (using naive for demo):");
        System.out.println("Mod-0 positions: " + Arrays.toString(new int[]{0,3,6,9}));
        System.out.println("Mod-1 positions: " + Arrays.toString(new int[]{1,4,7,10}));
        System.out.println("Mod-2 positions: " + Arrays.toString(new int[]{2,5,8,11}));
        for (int i : sa) System.out.println(i + " (mod " + i%3 + "): " + s.substring(i));
    }
}
