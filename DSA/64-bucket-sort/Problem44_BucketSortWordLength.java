import java.util.*;
public class Problem44_BucketSortWordLength {
    public String[] sortByWordLength(String[] words) {
        int max=0; for(String w:words) max=Math.max(max,w.length());
        List<String>[] buckets=new List[max+1]; for(int i=0;i<=max;i++) buckets[i]=new ArrayList<>();
        for(String w:words) buckets[w.length()].add(w);
        int idx=0; for(List<String> b:buckets) for(String w:b) words[idx++]=w;
        return words;
    }
    public static void main(String[] args){ System.out.println(Arrays.toString(new Problem44_BucketSortWordLength().sortByWordLength(new String[]{"the","quick","brown","fox","jumps"}))); }
}
