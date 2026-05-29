import java.util.*;
public class Problem24_SortByAbsoluteValue {
    public void sortByAbs(int[] arr) { Integer[] boxed=new Integer[arr.length]; for(int i=0;i<arr.length;i++) boxed[i]=arr[i]; Arrays.sort(boxed,(a,b)->Math.abs(a)-Math.abs(b)); for(int i=0;i<arr.length;i++) arr[i]=boxed[i]; }
    public static void main(String[] args){ int[] a={-5,3,-2,8,-1,4}; new Problem24_SortByAbsoluteValue().sortByAbs(a); System.out.println(Arrays.toString(a)); }
}
