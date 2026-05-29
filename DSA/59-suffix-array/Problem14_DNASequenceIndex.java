import java.util.*;

public class Problem14_DNASequenceIndex {
    // Index DNA sequence for fast pattern search
    int[] sa;
    String dna;

    public Problem14_DNASequenceIndex(String dna) {
        this.dna = dna;
        int n = dna.length();
        Integer[] saI = new Integer[n];
        for (int i = 0; i < n; i++) saI[i] = i;
        Arrays.sort(saI, (a, b) -> dna.substring(a).compareTo(dna.substring(b)));
        sa = Arrays.stream(saI).mapToInt(i->i).toArray();
    }

    public List<Integer> findPattern(String pattern) {
        int lo = lowerBound(pattern), hi = upperBound(pattern);
        List<Integer> result = new ArrayList<>();
        for (int i = lo; i < hi; i++) result.add(sa[i]);
        Collections.sort(result);
        return result;
    }

    int lowerBound(String p) {
        int lo=0,hi=sa.length;
        while(lo<hi){int m=(lo+hi)/2;String sub=dna.substring(sa[m],Math.min(sa[m]+p.length(),dna.length()));if(sub.compareTo(p)<0)lo=m+1;else hi=m;}
        return lo;
    }
    int upperBound(String p) {
        int lo=0,hi=sa.length;
        while(lo<hi){int m=(lo+hi)/2;String sub=dna.substring(sa[m],Math.min(sa[m]+p.length(),dna.length()));if(sub.compareTo(p)<=0)lo=m+1;else hi=m;}
        return lo;
    }

    public static void main(String[] args) {
        Problem14_DNASequenceIndex idx = new Problem14_DNASequenceIndex("AGATCGATCGATCAGATC");
        System.out.println("GATC found at: " + idx.findPattern("GATC"));
        System.out.println("AGATC found at: " + idx.findPattern("AGATC"));
    }
}
