import java.util.*;
public class Problem43_BucketSortLetterFrequency {
    public String sortByFrequency(String s) {
        int[] freq=new int[26]; for(char c:s.toCharArray()) freq[c-'a']++;
        List<Character>[] buckets=new List[s.length()+1]; for(int i=0;i<buckets.length;i++) buckets[i]=new ArrayList<>();
        for(int i=0;i<26;i++) if(freq[i]>0) buckets[freq[i]].add((char)(i+'a'));
        StringBuilder sb=new StringBuilder();
        for(int i=buckets.length-1;i>=0;i--) for(char c:buckets[i]) for(int j=0;j<i;j++) sb.append(c);
        return sb.toString();
    }
    public static void main(String[] args){ System.out.println(new Problem43_BucketSortLetterFrequency().sortByFrequency("programming")); }
}
