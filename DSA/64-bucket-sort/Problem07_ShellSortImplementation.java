import java.util.*;
public class Problem07_ShellSortImplementation {
    public void shellSort(int[] arr) {
        int n=arr.length;
        for(int gap=n/2;gap>0;gap/=2)
            for(int i=gap;i<n;i++){int temp=arr[i],j=i;while(j>=gap&&arr[j-gap]>temp){arr[j]=arr[j-gap];j-=gap;}arr[j]=temp;}
    }
    public static void main(String[] args){
        Problem07_ShellSortImplementation s=new Problem07_ShellSortImplementation();
        int[] arr={12,34,54,2,3};
        s.shellSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}
