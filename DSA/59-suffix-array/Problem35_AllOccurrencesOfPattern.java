import java.util.*;

public class Problem35_AllOccurrencesOfPattern {
    public static List<Integer> findAll(String text, String pattern) {
        int n = text.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->text.substring(a).compareTo(text.substring(b)));
        int lo = lowerBound(text, sa, pattern), hi = upperBound(text, sa, pattern);
        List<Integer> result = new ArrayList<>();
        for (int i = lo; i < hi; i++) result.add(sa[i]);
        Collections.sort(result);
        return result;
    }

    static int lowerBound(String t, Integer[] sa, String p) {
        int lo=0,hi=sa.length; while(lo<hi){int m=(lo+hi)/2;String s=t.substring(sa[m],Math.min(sa[m]+p.length(),t.length()));if(s.compareTo(p)<0)lo=m+1;else hi=m;} return lo;
    }
    static int upperBound(String t, Integer[] sa, String p) {
        int lo=0,hi=sa.length; while(lo<hi){int m=(lo+hi)/2;String s=t.substring(sa[m],Math.min(sa[m]+p.length(),t.length()));if(s.compareTo(p)<=0)lo=m+1;else hi=m;} return lo;
    }

    public static void main(String[] args) {
        System.out.println(findAll("abcabcabc", "abc")); // [0,3,6]
        System.out.println(findAll("aaaa", "aa")); // [0,1,2]
    }
}
