import java.util.*;
public class Problem18_RadixSortStrings {
    /* MSD Radix sort for strings */
    public void sort(String[] arr) {
        int maxLen=0; for(String s:arr) maxLen=Math.max(maxLen,s.length());
        // Pad strings
        String[] padded=new String[arr.length];
        for(int i=0;i<arr.length;i++) padded[i]=String.format("%-"+maxLen+"s",arr[i]);
        // LSD radix sort on characters
        for(int d=maxLen-1;d>=0;d--){
            int[] count=new int[256]; String[] output=new String[arr.length];
            for(String s:padded) count[s.charAt(d)]++;
            for(int i=1;i<256;i++) count[i]+=count[i-1];
            for(int i=padded.length-1;i>=0;i--){output[count[padded[i].charAt(d)]-1]=padded[i];count[padded[i].charAt(d)]--;}
            padded=output;
        }
        for(int i=0;i<arr.length;i++) arr[i]=padded[i].trim();
    }
    public static void main(String[] args){ Problem18_RadixSortStrings s=new Problem18_RadixSortStrings(); String[] a={"banana","apple","cherry","date","elderberry"}; s.sort(a); System.out.println(Arrays.toString(a)); }
}
