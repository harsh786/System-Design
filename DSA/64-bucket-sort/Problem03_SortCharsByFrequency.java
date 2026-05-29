import java.util.*;
public class Problem03_SortCharsByFrequency {
    public String frequencySort(String s) {
        int[] freq=new int[128]; for(char c:s.toCharArray()) freq[c]++;
        List<Character>[] buckets=new List[s.length()+1];
        for(int i=0;i<buckets.length;i++) buckets[i]=new ArrayList<>();
        for(int i=0;i<128;i++) if(freq[i]>0) buckets[freq[i]].add((char)i);
        StringBuilder sb=new StringBuilder();
        for(int i=buckets.length-1;i>=0;i--) for(char c:buckets[i]) for(int j=0;j<i;j++) sb.append(c);
        return sb.toString();
    }
    public static void main(String[] args){
        Problem03_SortCharsByFrequency s=new Problem03_SortCharsByFrequency();
        System.out.println(s.frequencySort("tree"));
    }
}
