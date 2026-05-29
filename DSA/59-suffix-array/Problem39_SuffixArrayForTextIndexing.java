import java.util.*;

public class Problem39_SuffixArrayForTextIndexing {
    // Full text search engine using suffix array
    int[] sa;
    String text;

    public Problem39_SuffixArrayForTextIndexing(String text) {
        this.text = text;
        int n = text.length();
        Integer[] saI = new Integer[n]; for(int i=0;i<n;i++)saI[i]=i;
        Arrays.sort(saI,(a,b)->text.substring(a).compareTo(text.substring(b)));
        sa = Arrays.stream(saI).mapToInt(i->i).toArray();
    }

    public List<int[]> search(String query) { // returns [start, end] of each match
        int lo=lowerBound(query), hi=upperBound(query);
        List<int[]> results = new ArrayList<>();
        for(int i=lo;i<hi;i++) results.add(new int[]{sa[i], sa[i]+query.length()});
        results.sort((a,b)->a[0]-b[0]);
        return results;
    }

    int lowerBound(String p){int lo=0,hi=sa.length;while(lo<hi){int m=(lo+hi)/2;String s=text.substring(sa[m],Math.min(sa[m]+p.length(),text.length()));if(s.compareTo(p)<0)lo=m+1;else hi=m;}return lo;}
    int upperBound(String p){int lo=0,hi=sa.length;while(lo<hi){int m=(lo+hi)/2;String s=text.substring(sa[m],Math.min(sa[m]+p.length(),text.length()));if(s.compareTo(p)<=0)lo=m+1;else hi=m;}return lo;}

    public static void main(String[] args) {
        Problem39_SuffixArrayForTextIndexing idx = new Problem39_SuffixArrayForTextIndexing("to be or not to be that is the question");
        for(int[] r : idx.search("to")) System.out.println("Found at ["+r[0]+","+r[1]+")");
        System.out.println("Count 'be': " + idx.search("be").size());
    }
}
