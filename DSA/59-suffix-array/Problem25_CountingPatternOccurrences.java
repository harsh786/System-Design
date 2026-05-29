import java.util.*;

public class Problem25_CountingPatternOccurrences {
    static int[] buildSA(String s) {
        int n=s.length(); Integer[] sa=new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    public static List<Integer> findAll(String text, String pat) {
        int[] sa = buildSA(text);
        int lo = 0, hi = sa.length - 1, start = sa.length, end = -1;
        // lower bound
        int l=0,h=sa.length; while(l<h){int m=(l+h)/2;String sub=text.substring(sa[m],Math.min(sa[m]+pat.length(),text.length()));if(sub.compareTo(pat)<0)l=m+1;else h=m;} start=l;
        l=0;h=sa.length; while(l<h){int m=(l+h)/2;String sub=text.substring(sa[m],Math.min(sa[m]+pat.length(),text.length()));if(sub.compareTo(pat)<=0)l=m+1;else h=m;} end=l;
        List<Integer> result = new ArrayList<>();
        for (int i = start; i < end; i++) result.add(sa[i]);
        Collections.sort(result);
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findAll("abababab", "aba")); // [0,2,4]
        System.out.println("Count: " + findAll("abababab", "aba").size());
    }
}
