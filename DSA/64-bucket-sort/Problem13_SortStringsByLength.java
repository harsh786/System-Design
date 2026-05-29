import java.util.*;
public class Problem13_SortStringsByLength {
    public String[] sortByLength(String[] strs) {
        int max=0; for(String s:strs) max=Math.max(max,s.length());
        List<String>[] buckets=new List[max+1]; for(int i=0;i<=max;i++) buckets[i]=new ArrayList<>();
        for(String s:strs) buckets[s.length()].add(s);
        int idx=0; for(List<String> b:buckets) for(String s:b) strs[idx++]=s;
        return strs;
    }
    public static void main(String[] args){ Problem13_SortStringsByLength s=new Problem13_SortStringsByLength(); System.out.println(Arrays.toString(s.sortByLength(new String[]{"hello","hi","hey","a","world"}))); }
}
