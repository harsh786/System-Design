import java.util.*;

public class Problem38_SuffixArrayForPlagiarismDetection {
    // Find common substrings longer than threshold between two documents
    public static List<String> detectPlagiarism(String doc1, String doc2, int minLen) {
        String s = doc1 + "\1" + doc2;
        int n = s.length(), sep = doc1.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        Set<String> matches = new TreeSet<>();
        for(int i=1;i<n;i++){
            if((sa[i-1]<sep)==(sa[i]<sep))continue;
            int lcp=0,a=sa[i-1],b=sa[i]; while(a+lcp<n&&b+lcp<n&&s.charAt(a+lcp)==s.charAt(b+lcp))lcp++;
            if(lcp>=minLen) matches.add(s.substring(sa[i],sa[i]+lcp));
        }
        return new ArrayList<>(matches);
    }

    public static void main(String[] args) {
        String doc1 = "the quick brown fox jumps over the lazy dog";
        String doc2 = "a quick brown fox leaps over a lazy cat";
        System.out.println(detectPlagiarism(doc1, doc2, 5));
    }
}
